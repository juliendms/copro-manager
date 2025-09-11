from flask import render_template, request, redirect, url_for, flash, abort, Blueprint, current_app, make_response
from models import db, Charge, Owner, OwnerEmail, ChargeRepartition
from datetime import datetime
from sqlalchemy.orm import joinedload, subqueryload
from charges_management.utils import get_services, get_account_info, send_message, render_owner
from google.auth.exceptions import RefreshError

from . import charges_bp


@charges_bp.route('/')
def list_charges():
    with current_app.app_context():
        charges = Charge.query.all()
    return render_template('charges.html', charges=charges)

@charges_bp.route('/fragments/table')
def table_fragment():
    charges = Charge.query.all()
    resp = make_response(render_template('partials/charges_table.html', charges=charges))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@charges_bp.route('/fragments/dialog')
def dialog_fragment():
    mode = request.args.get('mode', 'add')
    charge = None
    action_url = url_for('charges.add_charge')
    title = 'Add a charge'
    is_common = True  # Default for new charge
    owners = Owner.query.all()
    if mode == 'edit':
        charge_id = request.args.get('charge_id', type=int)
        if charge_id is None:
            abort(400)
        with current_app.app_context():
            charge = Charge.query.options(subqueryload(Charge.repartitions).joinedload(ChargeRepartition.owner)).get_or_404(charge_id)
        action_url = url_for('charges.edit_charge', charge_id=charge.id)
        title = 'Edit charge'
        is_common = charge.type == 'common'
    # Return dialog inner content directly; base has a single <dialog id="dialog">
    return render_template('charge_dialog.html',
                           title=title,
                           action_url=action_url,
                           charge=charge,
                           is_common=is_common,
                           owners=owners)

@charges_bp.route('/fragments/type_fields')
def type_fields():
    charge_type = request.args.get('type', 'common')
    charge = None
    charge_id = request.args.get('charge_id', type=int)
    if charge_id:
        with current_app.app_context():
            charge = Charge.query.options(subqueryload(Charge.repartitions).joinedload(ChargeRepartition.owner)).get_or_404(charge_id)
    is_common = charge_type == 'common'
    owners = Owner.query.all()
    return render_template('partials/_charge_type_selector.html', charge=charge, is_common=is_common, owners=owners)

@charges_bp.route('/add', methods=['POST'])
def add_charge():
    description = request.form['description']
    total_amount = float(request.form['total_amount'])
    charge_type = request.form['charge_type']
    voting_date_str = request.form['voting_date']
    voting_date = datetime.strptime(voting_date_str, '%Y-%m-%d').date()

    year = None
    purpose = None
    
    with current_app.app_context():
        new_charge = Charge(
            description=description,
            total_amount=total_amount,
            type=charge_type,
            voting_date=voting_date,
        )

        owners_to_associate = []
        if charge_type == 'common':
            new_charge.year = int(request.form['year'])
            owners_to_associate = Owner.query.all()
        elif charge_type == 'extraordinary':
            new_charge.purpose = request.form['purpose']
            owner_ids = request.form.getlist('owners')
            if owner_ids:
                owners_to_associate = Owner.query.filter(Owner.id.in_(owner_ids)).all()
        
        for owner in owners_to_associate:
            repartition = ChargeRepartition(owner=owner)
            new_charge.repartitions.append(repartition)

        db.session.add(new_charge)
        db.session.commit()
        flash('Charge added successfully!', 'success')
        if request.headers.get('HX-Request'):
            response = make_response(render_template('partials/charges_table.html', charges=Charge.query.all()))
            response.headers['HX-Trigger'] = 'flash-refresh,charge-changed,closeDialog'
            return response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return '', 201
        return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/edit', methods=['POST'])
def edit_charge(charge_id):
    with current_app.app_context():
        charge = Charge.query.options(subqueryload(Charge.repartitions)).get_or_404(charge_id)
        charge.description = request.form['description']
        charge.total_amount = float(request.form['total_amount'])
        charge.type = request.form['charge_type']
        charge.voting_date = datetime.strptime(request.form['voting_date'], '%Y-%m-%d').date()

        if charge.type == 'common':
            charge.year = int(request.form['year'])
            charge.purpose = None
            owners_to_associate = Owner.query.all()
        elif charge.type == 'extraordinary':
            charge.purpose = request.form['purpose']
            charge.year = None
            owner_ids_str = request.form.getlist('owners')
            if owner_ids_str:
                owner_ids = {int(id) for id in owner_ids_str}
                owners_to_associate = Owner.query.filter(Owner.id.in_(owner_ids)).all()
            else:
                owners_to_associate = []

        existing_owner_ids = {rep.owner_id for rep in charge.repartitions}
        new_owner_ids = {owner.id for owner in owners_to_associate}

        # Remove owners who are no longer associated
        for owner_id_to_remove in existing_owner_ids - new_owner_ids:
            repartition_to_remove = next((rep for rep in charge.repartitions if rep.owner_id == owner_id_to_remove), None)
            if repartition_to_remove:
                db.session.delete(repartition_to_remove)

        # Add new owners
        for owner_id_to_add in new_owner_ids - existing_owner_ids:
            owner_to_add = next((owner for owner in owners_to_associate if owner.id == owner_id_to_add), None)
            if owner_to_add:
                repartition = ChargeRepartition(owner=owner_to_add, charge=charge)
                db.session.add(repartition)

        db.session.commit()
        flash('Charge updated successfully!', 'success')
        if request.headers.get('HX-Request'):
            response = make_response(render_template('partials/charges_table.html', charges=Charge.query.all()))
            response.headers['HX-Trigger'] = 'flash-refresh,charge-changed,closeDialog'
            return response
        if request.headers.get('X-Requested-with') == 'XMLHttpRequest':
            return '', 201
        return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/delete', methods=['POST', 'DELETE'])
def delete_charge(charge_id):
    with current_app.app_context():
        charge = Charge.query.get_or_404(charge_id)
        db.session.delete(charge)
        db.session.commit()
        flash('Charge deleted successfully!', 'success')
        if request.headers.get('HX-Request'):
            response = make_response(render_template('partials/charges_table.html', charges=Charge.query.all()))
            response.headers['HX-Trigger'] = 'flash-refresh,charge-changed'
            return response
    return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/repartition')
def view_repartition(charge_id):
    with current_app.app_context():
        charge = Charge.query.options(
            subqueryload(Charge.repartitions).joinedload(ChargeRepartition.owner).joinedload(Owner.emails)
        ).get_or_404(charge_id)
        
        owners_for_total_shares = [rep.owner for rep in charge.repartitions]
        total_shares = sum(owner.share for owner in owners_for_total_shares)

        repartition_details = []
        for repartition in charge.repartitions:
            if total_shares > 0:
                owner_amount = (repartition.owner.share / total_shares) * charge.total_amount
            else:
                owner_amount = 0.0
            repartition_details.append({
                'repartition': repartition,
                'amount': owner_amount
            })

    return render_template('repartition.html', charge=charge, repartition_details=repartition_details)


@charges_bp.route('/<int:charge_id>/repartition/send_email/<int:owner_id>', methods=['POST'])
def send_repartition_email(charge_id, owner_id):
    with current_app.app_context():
        repartition = db.session.get(ChargeRepartition, {'charge_id': charge_id, 'owner_id': owner_id})
        if not repartition:
            abort(404)

        charge = repartition.charge
        owner = repartition.owner

        owners_for_charge = [rep.owner for rep in charge.repartitions]
        total_shares = sum(o.share for o in owners_for_charge)
        if total_shares > 0:
            owner_amount = (owner.share / total_shares) * charge.total_amount
        else:
            owner_amount = 0.0

        # Prepare context for the email template
        context = {
            'title': charge.description,
            'name': owner.name,
            'lot': owner.lot_number,
            'share': str(owner.share),
            'amount_due': "%.2f" % owner_amount,
            'description': charge.description,
            'total_charge_amount': "%.2f" % charge.total_amount,
            'voting_date': charge.voting_date.strftime('%Y-%m-%d'),
            'total_budget': "%.2f" % charge.total_amount # This seems to be duplicated, might be good to review later
        }

        email_template = ''
        if charge.type == 'common':
            context['year'] = charge.year
            email_template = 'email_common_charges.html'
        elif charge.type == 'extraordinary':
            context['purpose'] = charge.purpose
            email_template = 'email_extraordinary_charges.html'

        html = render_template(email_template, **context)

        recipients = [email_obj.email for email_obj in owner.emails]
        if not recipients:
            flash(f"No email addresses found for {owner.name}.", 'danger')
            return redirect(url_for('charges.view_repartition', charge_id=charge_id))

        try:
            creds, gmail, oauth2 = get_services()
            account_email, account_name = get_account_info(oauth2)

            if not account_email:
                flash("Unable to retrieve sender account info for email. Ensure token.json has correct scopes.", 'danger')
                print("DEBUG: account_email is empty.")
                return redirect(url_for('charges.view_repartition', charge_id=charge_id))

            subject = charge.description
            resp = send_message(gmail, recipients, subject, html, account_email, account_name)
            
            repartition.email_sent_date = datetime.utcnow()
            db.session.commit()
            
            flash(f"Email sent to {owner.name} successfully!", 'success')
            print(f"DEBUG: Email sent successfully! Response: {resp}")
        except RefreshError as e:
            flash(f"Authentication error for email service: {e}. Please re-run oauth_setup.py", 'danger')
            print(f"DEBUG: RefreshError: {e}")
        except Exception as e:
            flash(f"Error sending email to {owner.name}: {e}", 'danger')
            print(f"DEBUG: General Exception during email send: {e}")

        if request.headers.get('HX-Request'):
            repartition_details = {
                'repartition': repartition,
                'amount': owner_amount
            }
            return render_template('partials/_repartition_row.html', detail=repartition_details, charge=charge)

        return redirect(url_for('charges.view_repartition', charge_id=charge_id))


@charges_bp.route('/<int:charge_id>/repartition/mark_as_paid/<int:owner_id>', methods=['POST'])
def mark_as_paid(charge_id, owner_id):
    with current_app.app_context():
        repartition = db.session.get(ChargeRepartition, {'charge_id': charge_id, 'owner_id': owner_id})
        if not repartition:
            abort(404)
        
        repartition.paid_date = datetime.utcnow()
        db.session.commit()

        charge = repartition.charge

        owners_for_charge = [rep.owner for rep in charge.repartitions]
        total_shares = sum(o.share for o in owners_for_charge)
        if total_shares > 0:
            owner_amount = (repartition.owner.share / total_shares) * charge.total_amount
        else:
            owner_amount = 0.0

        if request.headers.get('HX-Request'):
            repartition_details = {
                'repartition': repartition,
                'amount': owner_amount
            }
            return render_template('partials/_repartition_row.html', detail=repartition_details, charge=charge)

        return redirect(url_for('charges.view_repartition', charge_id=charge_id))
