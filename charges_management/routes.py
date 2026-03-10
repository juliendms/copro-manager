from flask import render_template, request, redirect, url_for, flash, abort, Blueprint, current_app, make_response
from models import db, Charge, Owner, OwnerEmail, ChargeRepartition, PaymentInstallment, LimitedCommonElement, LCEShare
from datetime import datetime, timezone
from sqlalchemy.orm import joinedload, subqueryload
from charges_management.utils import get_services, get_account_info, send_message, render_owner
from google.auth.exceptions import RefreshError

from . import charges_bp
from app_utils import no_cache


def _resolve_owners_and_shares(charge_type, lce_id):
    """Return list of (Owner, share) tuples and the resolved LCE id based on scope.

    Common charges → all owners with general_share, lce_id forced to None.
    Extraordinary charges → general (all owners) or LCE-scoped.
    """
    if charge_type == 'common' or not lce_id:
        owners = Owner.query.all()
        return [(o, o.general_share) for o in owners], None
    else:
        lce = LimitedCommonElement.query.get_or_404(int(lce_id))
        return [(ls.owner, ls.share) for ls in lce.shares], lce.id


def _populate_repartitions(db_session, charge, owners_and_shares):
    """Create ChargeRepartition + PaymentInstallment rows for a charge."""
    total_shares = sum(s for _, s in owners_and_shares)

    for owner, share in owners_and_shares:
        rep = ChargeRepartition(
            charge_id=charge.id,
            owner_id=owner.id,
            share_snapshot=share,
        )
        db_session.add(rep)
        db_session.flush()

        owner_amount = (share / total_shares) * charge.total_amount if total_shares > 0 else 0

        if charge.payment_schedule == 'quarterly':
            quarterly_amount = owner_amount / 4
            for q in range(1, 5):
                db_session.add(PaymentInstallment(
                    charge_repartition_charge_id=charge.id,
                    charge_repartition_owner_id=owner.id,
                    quarter=q,
                    amount=quarterly_amount,
                ))
        else:
            db_session.add(PaymentInstallment(
                charge_repartition_charge_id=charge.id,
                charge_repartition_owner_id=owner.id,
                quarter=None,
                amount=owner_amount,
            ))


@charges_bp.route('/')
def list_charges():
    with current_app.app_context():
       charges = Charge.query.all()
    has_charges = len(charges) > 0
    return render_template('charges.html', charges=charges, has_charges=has_charges)

@charges_bp.route('/fragments/table')
@no_cache
def table_fragment():
    charges = Charge.query.all()
    resp = make_response(render_template('partials/charges_table.html', charges=charges))
    return resp

@charges_bp.route('/fragments/dialog')
def dialog_fragment():
    mode = request.args.get('mode', 'add')
    target = request.args.get('target', 'charge_table')
    charge = None
    action_url = url_for('charges.add_charge')
    title = 'Add a charge'
    is_common = True
    lce_list = LimitedCommonElement.query.all()

    if target == 'repartition':
        form_hx_target = 'this'
    elif target == 'charge_page':
        form_hx_target = '#content'
    else:
        form_hx_target = '#charges-table'

    if mode == 'edit':
        charge_id = request.args.get('charge_id', type=int)
        if charge_id is None:
            abort(400)
        with current_app.app_context():
            charge = Charge.query.options(subqueryload(Charge.repartitions)).get_or_404(charge_id)
        action_url = url_for('charges.edit_charge', charge_id=charge.id)
        title = 'Edit charge'
        is_common = charge.type == 'common'

    return render_template('charge_dialog.html',
                           title=title,
                           action_url=action_url,
                           charge=charge,
                           is_common=is_common,
                           lce_list=lce_list,
                           form_hx_target=form_hx_target,
                           form_hx_swap='innerHTML')

@charges_bp.route('/fragments/type_fields')
def type_fields():
    charge_type = request.args.get('type', 'common')
    charge = None
    charge_id = request.args.get('charge_id', type=int)
    if charge_id:
        with current_app.app_context():
            charge = Charge.query.options(subqueryload(Charge.repartitions)).get_or_404(charge_id)
    is_common = charge_type == 'common'
    lce_list = LimitedCommonElement.query.all()
    return render_template('partials/_charge_type_selector.html', charge=charge, is_common=is_common, lce_list=lce_list)

@charges_bp.route('/add', methods=['POST'])
def add_charge():
    description = request.form['description']
    total_amount = float(request.form['total_amount'])
    charge_type = request.form['charge_type']

    voting_date = None
    if request.form.get('voting_date'):
        voting_date_str = request.form['voting_date']
        voting_date = datetime.strptime(voting_date_str, '%Y-%m-%d').date()

    payment_schedule = 'quarterly' if charge_type == 'common' else 'one_time'

    with current_app.app_context():
        new_charge = Charge(
            description=description,
            total_amount=total_amount,
            type=charge_type,
            payment_schedule=payment_schedule,
            voting_date=voting_date,
        )

        if charge_type == 'common':
            new_charge.year = int(request.form['year'])
            lce_id = None  # Common charges always general scope
        elif charge_type == 'extraordinary':
            new_charge.purpose = request.form['purpose']
            lce_id = request.form.get('limited_common_element_id') or None

        owners_and_shares, resolved_lce_id = _resolve_owners_and_shares(charge_type, lce_id)
        new_charge.limited_common_element_id = resolved_lce_id

        db.session.add(new_charge)
        db.session.flush()

        _populate_repartitions(db.session, new_charge, owners_and_shares)

        db.session.commit()
        flash('Charge added successfully!', 'success')

        if request.headers.get('HX-Request'):
            hx_target_header = request.headers.get('HX-Target')

            if hx_target_header == 'content':
                charges = Charge.query.all()
                has_charges = len(charges) > 0
                response_content = render_template('partials/charges_main_content.html', charges=charges, has_charges=has_charges)
                response = make_response(response_content)
                response.headers['HX-Trigger'] = 'flash-refresh,charge-changed,closeDialog'
                return response
            elif hx_target_header == 'charges-table':
                response = make_response(render_template('partials/charges_table.html', charges=Charge.query.all()))
                response.headers['HX-Trigger'] = 'flash-refresh,charge-changed,closeDialog'
                return response
            else:
                redirect_url = url_for('charges.view_repartition', charge_id=new_charge.id)
                response = make_response('<div id="redirect-placeholder" style="display:none;"></div>')
                response.headers['HX-Redirect'] = redirect_url
                response.headers['HX-Trigger'] = 'flash-refresh,closeDialog'
                return response

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return '', 201
        return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/edit', methods=['POST'])
def edit_charge(charge_id):
    with current_app.app_context():
        charge = Charge.query.options(subqueryload(Charge.repartitions)).get_or_404(charge_id)

        original_total_amount = charge.total_amount
        has_repartitions = len(charge.repartitions) > 0

        charge.description = request.form['description']
        charge.total_amount = float(request.form['total_amount'])

        if request.form.get('voting_date'):
            charge.voting_date = datetime.strptime(request.form['voting_date'], '%Y-%m-%d').date()
        else:
            charge.voting_date = None

        # Lock charge type and scope if repartitions exist
        if has_repartitions:
            charge_type = charge.type
        else:
            charge_type = request.form['charge_type']
            charge.type = charge_type
            charge.payment_schedule = 'quarterly' if charge_type == 'common' else 'one_time'

        if charge.type == 'common':
            charge.year = int(request.form['year'])
            charge.purpose = None
            charge.limited_common_element_id = None
        elif charge.type == 'extraordinary':
            charge.purpose = request.form['purpose']
            charge.year = None
            # LCE is locked once repartitions exist
            if not has_repartitions:
                lce_id = request.form.get('limited_common_element_id') or None
                _, resolved_lce_id = _resolve_owners_and_shares(charge.type, lce_id)
                charge.limited_common_element_id = resolved_lce_id

        amount_changed = (original_total_amount != charge.total_amount)

        if not has_repartitions:
            # Populate repartitions for the first time
            owners_and_shares, _ = _resolve_owners_and_shares(
                charge.type, charge.limited_common_element_id
            )
            _populate_repartitions(db.session, charge, owners_and_shares)

        elif amount_changed:
            # Only amount changed — recalculate using snapshotted shares
            total_shares = sum(rep.share_snapshot for rep in charge.repartitions)
            for rep in charge.repartitions:
                owner_amount = (rep.share_snapshot / total_shares) * charge.total_amount if total_shares > 0 else 0
                if charge.payment_schedule == 'quarterly':
                    quarterly_amount = owner_amount / 4
                    for inst in rep.installments:
                        inst.amount = quarterly_amount
                else:
                    for inst in rep.installments:
                        inst.amount = owner_amount

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
            charges = Charge.query.all()
            has_charges = len(charges) > 0
            response = make_response(render_template('partials/charges_table.html', charges=charges))
            response.headers['HX-Trigger'] = 'flash-refresh,charge-changed'
            if not has_charges:
                response.headers['HX-Refresh'] = 'true'
            return response
    return redirect(url_for('charges.list_charges'))

@charges_bp.route('/<int:charge_id>/repartition')
@no_cache
def view_repartition(charge_id):
    selected_quarter = request.args.get('quarter', type=int)

    with current_app.app_context():
        charge = Charge.query.options(
            subqueryload(Charge.repartitions).joinedload(ChargeRepartition.owner).joinedload(Owner.emails)
        ).get_or_404(charge_id)

        installments = []
        quarter_completion = {}

        if charge.payment_schedule == 'quarterly':
            all_installments = db.session.query(PaymentInstallment).join(ChargeRepartition).filter(
                ChargeRepartition.charge_id == charge_id
            ).options(
                joinedload(PaymentInstallment.charge_repartition).joinedload(ChargeRepartition.owner).joinedload(Owner.emails)
            ).order_by(PaymentInstallment.quarter, ChargeRepartition.owner_id).all()

            for i in range(1, 5):
                quarter_installments = [inst for inst in all_installments if inst.quarter == i]
                if quarter_installments:
                    quarter_completion[i] = all(inst.status == 'Paid' for inst in quarter_installments)
                else:
                    quarter_completion[i] = False

            if selected_quarter is None:
                for i in range(1, 5):
                    if not quarter_completion.get(i, True):
                        selected_quarter = i
                        break
                if selected_quarter is None:
                    selected_quarter = 4

            installments = [inst for inst in all_installments if inst.quarter == selected_quarter]

        else: # one_time
            installments = db.session.query(PaymentInstallment).join(ChargeRepartition).filter(
                ChargeRepartition.charge_id == charge_id
            ).options(
                joinedload(PaymentInstallment.charge_repartition).joinedload(ChargeRepartition.owner).joinedload(Owner.emails)
            ).all()

    return render_template('repartition.html',
                           charge=charge,
                           installments=installments,
                           selected_quarter=selected_quarter,
                           quarter_completion=quarter_completion)


def _get_quarter_completion(charge_id):
    """Helper function to calculate the completion status for each quarter of a charge."""
    quarter_completion = {}
    all_installments = db.session.query(PaymentInstallment).join(ChargeRepartition).filter(
        ChargeRepartition.charge_id == charge_id
    ).all()

    for i in range(1, 5):
        quarter_installments = [inst for inst in all_installments if inst.quarter == i]
        if quarter_installments:
            quarter_completion[i] = all(inst.status == 'Paid' for inst in quarter_installments)
        else:
            quarter_completion[i] = False
    return quarter_completion


@charges_bp.route('/<int:charge_id>/repartition/nav')
def quarter_nav_fragment(charge_id):
    """Renders the quarter navigation fragment."""
    selected_quarter = request.args.get('selected_quarter', type=int)
    charge = Charge.query.get_or_404(charge_id)
    quarter_completion = _get_quarter_completion(charge_id)

    return render_template('partials/_quarter_nav.html',
                           charge=charge,
                           selected_quarter=selected_quarter,
                           quarter_completion=quarter_completion)


@charges_bp.route('/repartition/installment/<int:installment_id>/send_email', methods=['POST'])
def send_repartition_email(installment_id):
    with current_app.app_context():
        installment = PaymentInstallment.query.options(
            joinedload(PaymentInstallment.charge_repartition).joinedload(ChargeRepartition.charge)
        ).get_or_404(installment_id)
        charge = installment.charge_repartition.charge
        owner = installment.charge_repartition.owner

        # Calculate the total yearly amount for this owner and charge
        all_owner_installments = PaymentInstallment.query.join(ChargeRepartition).filter(
            ChargeRepartition.charge_id == charge.id,
            ChargeRepartition.owner_id == owner.id
        ).all()
        yearly_amount = sum(inst.amount for inst in all_owner_installments)

        subject_prefix = "Rappel - " if installment.email_sent_date else ""
        subject_suffix = " - Trimestre " + str(installment.quarter) if installment.quarter else ""
        subject = f"{subject_prefix}{charge.description}{subject_suffix}"

        context = {
            'installment': installment,
            'yearly_amount': yearly_amount,
            'subject': subject
        }

        html = render_template('email_charges.html', **context)
        recipients = [email_obj.email for email_obj in owner.emails]
        if not recipients:
            flash(f"No email addresses found for {owner.name}.", 'danger')
            return render_template('partials/_repartition_row.html', installment=installment, charge=charge)

        try:
            creds, gmail, oauth2 = get_services()
            account_email, account_name = get_account_info(oauth2)

            send_message(gmail, recipients, subject, html, account_email, account_name)

            installment.email_sent_date = datetime.now(timezone.utc)
            db.session.commit()

            flash(f"Email sent to {owner.name} successfully!", 'success')
        except RefreshError as e:
            flash(f"Authentication error for email service: {e}. Please re-run oauth_setup.py", 'danger')
        except Exception as e:
            flash(f"Error sending email to {owner.name}: {e}", 'danger')

        if request.headers.get('HX-Request'):
            installment_with_relations = PaymentInstallment.query.options(
                joinedload(PaymentInstallment.charge_repartition).joinedload(ChargeRepartition.owner).joinedload(Owner.emails)
            ).get(installment_id)
            response = make_response(render_template('partials/_repartition_row.html', installment=installment_with_relations, charge=charge))
            response.headers['HX-Trigger'] = 'flash-refresh'
            return response

        return redirect(url_for('charges.view_repartition', charge_id=charge.id))


@charges_bp.route('/repartition/installment/<int:installment_id>/mark_as_paid', methods=['POST'])
def mark_as_paid(installment_id):
    with current_app.app_context():
        installment = PaymentInstallment.query.get_or_404(installment_id)

        installment.paid_date = datetime.now(timezone.utc)
        db.session.commit()

        charge = installment.charge_repartition.charge

        if request.headers.get('HX-Request'):
            installment_with_relations = PaymentInstallment.query.options(
                joinedload(PaymentInstallment.charge_repartition).joinedload(ChargeRepartition.owner).joinedload(Owner.emails)
            ).get(installment_id)

            html = render_template('partials/_repartition_row.html', installment=installment_with_relations, charge=charge)
            response = make_response(html)

            if installment.quarter:
                quarter_completion = _get_quarter_completion(charge.id)
                if quarter_completion.get(installment.quarter, False):
                    response.headers['HX-Trigger'] = 'quarter-completed'

            return response

        return redirect(url_for('charges.view_repartition', charge_id=charge.id))
