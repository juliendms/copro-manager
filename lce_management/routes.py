from flask import render_template, request, redirect, url_for, flash, abort, make_response
from models import db, LimitedCommonElement, LCEShare, Owner
from sqlalchemy.orm import joinedload

from . import lce_bp
from app_utils import no_cache


@lce_bp.route('/')
@no_cache
def list_lces():
    lces = LimitedCommonElement.query.options(joinedload(LimitedCommonElement.shares)).all()
    has_lces = len(lces) > 0
    return render_template('lce_list.html', lces=lces, has_lces=has_lces)


@lce_bp.route('/fragments/table')
@no_cache
def table_fragment():
    lces = LimitedCommonElement.query.options(joinedload(LimitedCommonElement.shares)).all()
    return render_template('partials/lce_table.html', lces=lces)


@lce_bp.route('/fragments/dialog')
def dialog_fragment():
    mode = request.args.get('mode', 'add')
    target = request.args.get('target', 'lce_table')
    lce = None
    action_url = url_for('lce.add_lce')
    title = 'Add an element'

    if target == 'lce_page':
        form_hx_target = '#content'
    else:
        form_hx_target = '#lce-table'

    owners = Owner.query.order_by(Owner.lot_number).all()
    shares_map = {}
    active_owner_ids = set()

    if mode == 'edit':
        lce_id = request.args.get('lce_id', type=int)
        if lce_id is None:
            abort(400)
        lce = LimitedCommonElement.query.get_or_404(lce_id)
        action_url = url_for('lce.edit_lce', lce_id=lce.id)
        title = 'Edit element'
        existing = LCEShare.query.filter_by(element_id=lce.id).all()
        shares_map = {s.owner_id: s.share for s in existing}
        active_owner_ids = set(shares_map.keys())

    return render_template('lce_dialog.html',
                           title=title,
                           action_url=action_url,
                           lce=lce,
                           owners=owners,
                           shares_map=shares_map,
                           active_owner_ids=active_owner_ids,
                           form_hx_target=form_hx_target,
                           form_hx_swap='innerHTML')


@lce_bp.route('/add', methods=['POST'])
def add_lce():
    name = request.form['name']

    lce = LimitedCommonElement(name=name)
    db.session.add(lce)
    db.session.flush()

    for key in request.form:
        if key.startswith('member_'):
            owner_id = int(key.split('_', 1)[1])
            share_val = request.form.get(f'share_{owner_id}', '').strip()
            if share_val:
                db.session.add(LCEShare(element_id=lce.id, owner_id=owner_id, share=int(share_val)))

    db.session.commit()
    flash('Element added successfully!', 'success')

    if request.headers.get('HX-Request'):
        hx_target = request.headers.get('HX-Target')
        if hx_target == 'content':
            lces = LimitedCommonElement.query.options(joinedload(LimitedCommonElement.shares)).all()
            response = make_response(render_template('partials/lce_main_content.html', lces=lces, has_lces=True))
        else:
            lces = LimitedCommonElement.query.options(joinedload(LimitedCommonElement.shares)).all()
            response = make_response(render_template('partials/lce_table.html', lces=lces))
        response.headers['HX-Trigger'] = 'flash-refresh,lce-changed,closeDialog'
        return response
    return redirect(url_for('lce.list_lces'))


@lce_bp.route('/<int:lce_id>/edit', methods=['POST'])
def edit_lce(lce_id):
    lce = LimitedCommonElement.query.options(
        joinedload(LimitedCommonElement.shares)
    ).get_or_404(lce_id)
    lce.name = request.form['name']

    new_shares = {}
    for key in request.form:
        if key.startswith('member_'):
            owner_id = int(key.split('_', 1)[1])
            share_val = request.form.get(f'share_{owner_id}', '').strip()
            if share_val:
                new_shares[owner_id] = int(share_val)

    existing = {s.owner_id: s for s in lce.shares}
    for owner_id, s in existing.items():
        if owner_id not in new_shares:
            db.session.delete(s)
    for owner_id, val in new_shares.items():
        if owner_id in existing:
            existing[owner_id].share = val
        else:
            db.session.add(LCEShare(element_id=lce.id, owner_id=owner_id, share=val))

    db.session.commit()
    flash('Element updated successfully!', 'success')

    if request.headers.get('HX-Request'):
        lces = LimitedCommonElement.query.options(joinedload(LimitedCommonElement.shares)).all()
        response = make_response(render_template('partials/lce_table.html', lces=lces))
        response.headers['HX-Trigger'] = 'flash-refresh,lce-changed,closeDialog'
        return response
    return redirect(url_for('lce.list_lces'))


@lce_bp.route('/<int:lce_id>/delete', methods=['POST', 'DELETE'])
def delete_lce(lce_id):
    lce = LimitedCommonElement.query.get_or_404(lce_id)
    if lce.charges:
        flash('Cannot delete element: it has associated charges.', 'danger')
        if request.headers.get('HX-Request'):
            response = make_response('', 409)
            response.headers['HX-Trigger'] = 'flash-refresh'
            return response
        return redirect(url_for('lce.list_lces'))

    db.session.delete(lce)
    db.session.commit()
    flash('Element deleted successfully!', 'success')

    if request.headers.get('HX-Request'):
        lces = LimitedCommonElement.query.options(joinedload(LimitedCommonElement.shares)).all()
        has_lces = len(lces) > 0
        response = make_response(render_template('partials/lce_table.html', lces=lces))
        response.headers['HX-Trigger'] = 'flash-refresh,lce-changed'
        if not has_lces:
            response.headers['HX-Refresh'] = 'true'
        return response
    return redirect(url_for('lce.list_lces'))
