from logging import debug
from flask import render_template, request, redirect, url_for, flash, Blueprint, make_response
import json
import os

from sqlalchemy.orm import joinedload

from . import owner_bp as owner
from models import db, Owner, OwnerEmail
from app_utils import no_cache


@owner.route('/')
@no_cache
def list_owners():
    owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()
    has_owners = len(owners) > 0
    return render_template('owners.html', owners=owners, has_owners=has_owners)

@owner.route('/fragments/table')
@no_cache
def table_fragment():
    owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()
    return render_template('partials/owners_table.html', owners=owners)

@owner.route('/fragments/dialog')
def dialog_fragment():
    mode = request.args.get('mode', 'add')
    owner = None
    action_url = url_for('owner.add_owner')
    title = 'Add an owner'
    form_hx_target = request.args.get('form_hx_target', '#owners-table') # Get hx_target_for_form
    if mode == 'edit':
        owner_id = request.args.get('owner_id', type=int)
        if owner_id:
            owner = Owner.query.get_or_404(owner_id)
            action_url = url_for('owner.edit_owner', owner_id=owner.id)
            title = 'Edit owner'
    return render_template('owner_dialog.html', title=title, action_url=action_url, owner=owner, form_hx_target=form_hx_target, form_hx_swap='innerHTML') # Pass form_hx_target and form_hx_swap

@owner.route('/add', methods=['POST'])
def add_owner():
    name = request.form['name']
    lot_number = request.form['lot_number']
    share = int(request.form['share'])
    emails_str = request.form['emails']
    form_hx_target = request.headers.get('HX-Target', '#owners-table') # Get HX-Target from headers if not explicitly passed

    existing_owner = Owner.query.filter_by(lot_number=lot_number).first()
    if existing_owner:
        flash(f"An owner with lot number {lot_number} already exists!", 'danger')
        if request.headers.get('HX-Request'):
            response = make_response('', 409)
            response.headers['HX-Trigger'] = 'flash-refresh'
            return response
        return redirect(url_for('owner.list_owners'))

    new_owner = Owner(name=name, lot_number=lot_number, share=share)
    db.session.add(new_owner)
    db.session.flush()

    email_list = [e.strip() for e in emails_str.split(',') if e.strip()]
    for email_address in email_list:
        existing_email_entry = OwnerEmail.query.filter_by(email=email_address).first()
        if not existing_email_entry:
            owner_email = OwnerEmail(email=email_address, owner=new_owner)
            db.session.add(owner_email)
        else:
            flash(f"Email {email_address} already exists for another owner. Skipping.", 'warning')

    db.session.commit()
    flash('Owner added successfully!', 'success')
    if request.headers.get('HX-Request'):
        owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()
        
        # Determine what to render based on form_hx_target
        if form_hx_target == 'content': # Check for the main#content target without the hash
            response_content = render_template('partials/owners_main_content.html', owners=owners)
        else: # Default to owners-table
            response_content = render_template('partials/owners_table.html', owners=owners)

        response = make_response(response_content)
        response.headers['HX-Trigger'] = 'flash-refresh,owner-changed,closeDialog'
        return response
    return redirect(url_for('owner.list_owners'))

@owner.route('/<int:owner_id>/edit', methods=['POST'])
def edit_owner(owner_id):
    owner = Owner.query.get_or_404(owner_id)
    owner.name = request.form['name']
    owner.lot_number = request.form['lot_number']
    owner.share = int(request.form['share'])
    emails_str = request.form['emails']

    # Check for lot number collision if it has changed
    if owner.lot_number != request.form['lot_number']:
        existing_owner = Owner.query.filter(Owner.id != owner_id, Owner.lot_number == request.form['lot_number']).first()
        if existing_owner:
            flash(f"An owner with lot number {request.form['lot_number']} already exists!", 'danger')
            if request.headers.get('HX-Request'):
                response = make_response('', 409)
                response.headers['HX-Trigger'] = 'flash-refresh'
                return response
            return redirect(url_for('owner.list_owners'))
    
    owner.lot_number = request.form['lot_number']
    owner.share = int(request.form['share'])

    OwnerEmail.query.filter_by(owner_id=owner.id).delete()
    db.session.flush()

    email_list = [e.strip() for e in emails_str.split(',') if e.strip()]
    for email_address in email_list:
        existing_email_entry = OwnerEmail.query.filter_by(email=email_address).first()
        if not existing_email_entry:
            owner_email = OwnerEmail(email=email_address, owner=owner)
            db.session.add(owner_email)
        else:
            flash(f"Email {email_address} already exists for another owner. Skipping.", 'warning')

    db.session.commit()
    flash('Owner updated successfully!', 'success')
    if request.headers.get('HX-Request'):
        owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()
        response = make_response(render_template('partials/owners_table.html', owners=owners))
        response.headers['HX-Trigger'] = 'flash-refresh,owner-changed,closeDialog'
        return response
    return redirect(url_for('owner.list_owners'))

@owner.route('/delete/<int:owner_id>', methods=['DELETE'])
def delete_owner(owner_id):
    owner = Owner.query.get_or_404(owner_id)
    db.session.delete(owner)
    db.session.commit()
    flash('Owner deleted successfully!', 'success')
    if request.headers.get('HX-Request'):
        owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()
        has_owners = len(owners) > 0
        response = make_response(render_template('partials/owners_table.html', owners=owners))
        response.headers['HX-Trigger'] = 'flash-refresh,owner-changed'
        if not has_owners:
            response.headers['HX-Refresh'] = 'true'
        return response
    return redirect(url_for('owner.list_owners'))

@owner.route('/init_data', methods=['GET', 'POST'])
def init_owner_data():
    json_file_path = os.path.join(owner.root_path, 'data', 'initial_owners.json')
    try:
        with open(json_file_path, 'r') as f:
            owner_data = json.load(f)
    except FileNotFoundError:
        flash("initial_owners.json not found in owner_management/data/", 'danger')
        response = make_response('') # Empty response with trigger for flash message
        response.headers['HX-Trigger'] = 'flash-refresh'
        return response
    except json.JSONDecodeError:
        flash("Error decoding initial_owners.json. Check file format.", 'danger')
        response = make_response('') # Empty response with trigger for flash message
        response.headers['HX-Trigger'] = 'flash-refresh'
        return response

    for data in owner_data:
        name = data["name"]
        lot_number = data["lot"]
        share = int(data["share"])
        emails_raw = data["email"]

        existing_owner = Owner.query.filter_by(name=name, lot_number=lot_number).first()
        if existing_owner:
            flash(f"Owner {name} (Lot {lot_number}) already exists, skipping.", 'info')
            owner_instance = existing_owner
        else:
            owner_instance = Owner(
                name=name,
                lot_number=lot_number,
                share=share
            )
            db.session.add(owner_instance)
            db.session.flush()

        email_list = [e.strip() for e in emails_raw.split(',') if e.strip()]
        for email_address in email_list:
            existing_email_entry = OwnerEmail.query.filter_by(email=email_address).first()
            if not existing_email_entry:
                owner_email = OwnerEmail(email=email_address, owner=owner_instance)
                db.session.add(owner_email)
            else:
                flash(f"  Email {email_address} already exists, skipping for {name}.", 'warning')
        
        db.session.commit()
    flash("Owner data initialization complete.", 'success')
    
    # Render the updated main content partial
    owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()
    response = make_response(render_template('partials/owners_main_content.html', owners=owners, has_owners=len(owners) > 0))
    response.headers['HX-Trigger'] = 'flash-refresh,owner-changed'
    return response
