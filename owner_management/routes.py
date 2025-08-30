from flask import render_template, request, redirect, url_for, flash, jsonify, Blueprint
import json # Import json to read the JSON file
import os # Import os for path manipulation

from sqlalchemy.orm import joinedload
from datetime import datetime

from . import owner_bp
from models import db, Owner, OwnerEmail # Changed to absolute import

@owner_bp.route('/')
def list_owners():
    owners = db.session.scalars(db.select(Owner).options(joinedload(Owner.emails))).unique().all()
    return render_template('owners.html', owners=owners)

@owner_bp.route('/add', methods=['POST'])
def add_owner():
    name = request.form['name']
    lot_number = request.form['lot_number']
    share = int(request.form['share'])
    emails_str = request.form['emails']

    existing_owner = Owner.query.filter_by(lot_number=lot_number).first()
    if existing_owner:
        flash(f"An owner with lot number {lot_number} already exists!", 'danger')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(message=f"An owner with lot number {lot_number} already exists!", category='danger'), 409
        return redirect(url_for('owner_bp.list_owners'))

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
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return '', 201
    return redirect(url_for('owner_bp.list_owners'))

@owner_bp.route('/<int:owner_id>/edit', methods=['POST'])
def edit_owner(owner_id):
    owner = Owner.query.get_or_404(owner_id)
    owner.name = request.form['name']
    owner.lot_number = request.form['lot_number']
    owner.share = int(request.form['share'])
    emails_str = request.form['emails']

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
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return '', 201
    return redirect(url_for('owner_bp.list_owners'))

@owner_bp.route('/delete/<int:owner_id>', methods=['POST'])
def delete_owner(owner_id):
    owner = Owner.query.get_or_404(owner_id)
    db.session.delete(owner)
    db.session.commit()
    flash('Owner deleted successfully!', 'success')
    return redirect(url_for('owner_bp.list_owners'))

@owner_bp.route('/init_data')
def init_owner_data():
    # Only allow initialization if no owners exist, or with a confirmation
    if Owner.query.first():
        flash("Owners already exist in the database. Skipping initialization.", 'info')
        return redirect(url_for('owner_bp.list_owners'))

    json_file_path = os.path.join(owner_bp.root_path, 'data', 'initial_owners.json')
    try:
        with open(json_file_path, 'r') as f:
            owner_data = json.load(f)
    except FileNotFoundError:
        flash("initial_owners.json not found in owner_management/data/", 'danger')
        return redirect(url_for('owner_bp.list_owners'))
    except json.JSONDecodeError:
        flash("Error decoding initial_owners.json. Check file format.", 'danger')
        return redirect(url_for('owner_bp.list_owners'))

    for data in owner_data:
        name = data["name"]
        lot_number = data["lot"]
        share = int(data["share"])
        emails_raw = data["email"]

        existing_owner = Owner.query.filter_by(name=name, lot_number=lot_number).first()
        if existing_owner:
            flash(f"Owner {name} (Lot {lot_number}) already exists, skipping.", 'info')
            owner = existing_owner
        else:
            owner = Owner(
                name=name,
                lot_number=lot_number,
                share=share
            )
            db.session.add(owner)
            db.session.flush()
            flash(f"Added owner: {name}", 'success')

        email_list = [e.strip() for e in emails_raw.split(',') if e.strip()]
        for email_address in email_list:
            existing_email_entry = OwnerEmail.query.filter_by(email=email_address).first()
            if not existing_email_entry:
                owner_email = OwnerEmail(email=email_address, owner=owner)
                db.session.add(owner_email)
                flash(f"  Added email: {email_address} for {name}", 'success')
            else:
                flash(f"  Email {email_address} already exists, skipping for {name}.", 'warning')
        
        db.session.commit()
        flash("Owner data initialization complete.", 'success')
    return redirect(url_for('owner_bp.list_owners'))
