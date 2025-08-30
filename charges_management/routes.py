from flask import render_template, request, redirect, url_for, flash, abort, Blueprint, current_app
from models import db, Charge, Owner, OwnerEmail
from datetime import datetime
from sqlalchemy.orm import joinedload
from charges_management.utils import get_services, get_account_info, send_message, render_owner
from google.auth.exceptions import RefreshError

from . import charges_bp


@charges_bp.route('/')
def list_charges():
    with current_app.app_context():
        charges = Charge.query.all()
    return render_template('charges.html', charges=charges)

@charges_bp.route('/add', methods=['POST'])
def add_charge():
    description = request.form['description']
    total_amount = float(request.form['total_amount'])
    charge_type = request.form['charge_type']
    voting_date_str = request.form['voting_date']
    voting_date = datetime.strptime(voting_date_str, '%Y-%m-%d').date()

    year = None
    purpose = None

    if charge_type == 'common':
        year = int(request.form['year'])
    elif charge_type == 'extraordinary':
        purpose = request.form['purpose']

    with current_app.app_context():
        new_charge = Charge(
            description=description,
            total_amount=total_amount,
            type=charge_type,
            year=year,
            purpose=purpose,
            voting_date=voting_date
        )
        db.session.add(new_charge)
        db.session.commit()
        flash('Charge added successfully!', 'success')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return '', 201
        return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/edit', methods=['POST'])
def edit_charge(charge_id):
    with current_app.app_context():
        charge = Charge.query.get_or_404(charge_id)
        charge.description = request.form['description']
        charge.total_amount = float(request.form['total_amount'])
        charge.type = request.form['charge_type']
        charge.voting_date = datetime.strptime(request.form['voting_date'], '%Y-%m-%d').date()

        if charge.type == 'common':
            charge.year = int(request.form['year'])
            charge.purpose = None
        elif charge.type == 'extraordinary':
            charge.purpose = request.form['purpose']
            charge.year = None

        db.session.commit()
        flash('Charge updated successfully!', 'success')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return '', 201
        return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/delete', methods=['POST'])
def delete_charge(charge_id):
    with current_app.app_context():
        charge = Charge.query.get_or_404(charge_id)
        db.session.delete(charge)
        db.session.commit()
        flash('Charge deleted successfully!', 'success')
    return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/repartition')
def view_repartition(charge_id):
    with current_app.app_context():
        charge = Charge.query.get_or_404(charge_id)
        owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()

        repartition_details = []
        total_shares = sum(owner.share for owner in owners)

        for owner in owners:
            if total_shares > 0:
                owner_amount = (owner.share / total_shares) * charge.total_amount
            else:
                owner_amount = 0.0
            repartition_details.append({
                'owner': owner,
                'amount': owner_amount
            })

    return render_template('repartition.html', charge=charge, repartition_details=repartition_details)


@charges_bp.route('/<int:charge_id>/repartition/send_email/<int:owner_id>', methods=['POST'])
def send_repartition_email(charge_id, owner_id):
    with current_app.app_context():
        charge = Charge.query.get_or_404(charge_id)
        owner = Owner.query.get_or_404(owner_id)

        total_shares = sum(o.share for o in Owner.query.all())
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
            creds, gmail, sheets, oauth2 = get_services()
            account_email, account_name = get_account_info(oauth2)

            if not account_email:
                flash("Unable to retrieve sender account info for email. Ensure token.json has correct scopes.", 'danger')
                print("DEBUG: account_email is empty.")
                return redirect(url_for('charges.view_repartition', charge_id=charge_id))

            subject = charge.description
            resp = send_message(gmail, recipients, subject, html, account_email, account_name)
            flash(f"Email sent to {owner.name} successfully!", 'success')
            print(f"DEBUG: Email sent successfully! Response: {resp}")
        except RefreshError as e:
            flash(f"Authentication error for email service: {e}. Please re-run oauth_setup.py", 'danger')
            print(f"DEBUG: RefreshError: {e}")
        except Exception as e:
            flash(f"Error sending email to {owner.name}: {e}", 'danger')
            print(f"DEBUG: General Exception during email send: {e}")

    return redirect(url_for('charges.view_repartition', charge_id=charge_id))
