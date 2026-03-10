"""Priority 2 — Extraordinary charge workflow tests (general + LCE scope).

Tests cover ADR-002: LCE-scoped charges and share snapshot behavior.
"""
from models import Charge, ChargeRepartition, PaymentInstallment, LimitedCommonElement, LCEShare
from tests.conftest import make_owner, make_lce, create_charge_with_repartitions


# --- General scope (no LCE) ---

def test_extraordinary_general_scope_covers_all_owners(app, db):
    """An extraordinary charge with no LCE should cover all owners."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    o2 = make_owner(db.session, 'Bob', 'B2', 200)

    owners = [(o1, o1.general_share), (o2, o2.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Roof repair', 3000.0, 'extraordinary',
        owners, purpose='Roof repair',
    )
    db.session.commit()

    assert charge.limited_common_element_id is None
    assert len(charge.repartitions) == 2
    assert charge.payment_schedule == 'one_time'


def test_extraordinary_general_scope_one_installment_per_owner(app, db):
    """Extraordinary (one_time) charges create 1 installment per owner."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    o2 = make_owner(db.session, 'Bob', 'B2', 300)

    owners = [(o1, o1.general_share), (o2, o2.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Roof repair', 4000.0, 'extraordinary',
        owners, purpose='Roof repair',
    )
    db.session.commit()

    alice_inst = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o1.id,
    ).all()
    assert len(alice_inst) == 1
    assert alice_inst[0].quarter is None
    # Alice: 100/400 * 4000 = 1000
    assert abs(alice_inst[0].amount - 1000.0) < 0.01


def test_extraordinary_general_scope_amounts(app, db):
    """Amounts must be proportional to general_share."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    o2 = make_owner(db.session, 'Bob', 'B2', 400)

    # Total shares = 500, total = 5000
    # Alice: 100/500 * 5000 = 1000
    # Bob:   400/500 * 5000 = 4000
    owners = [(o1, o1.general_share), (o2, o2.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Parking', 5000.0, 'extraordinary',
        owners, purpose='Parking repair',
    )
    db.session.commit()

    alice_inst = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o1.id,
    ).one()
    bob_inst = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o2.id,
    ).one()

    assert abs(alice_inst.amount - 1000.0) < 0.01
    assert abs(bob_inst.amount - 4000.0) < 0.01


# --- LCE scope ---

def test_extraordinary_lce_scope_covers_only_lce_members(app, db):
    """A charge scoped to an LCE should only include LCE members."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    o2 = make_owner(db.session, 'Bob', 'B2', 200)
    o3 = make_owner(db.session, 'Carol', 'C3', 300)

    # Only Alice and Bob are in the elevator LCE
    lce = make_lce(db.session, 'Elevator', [(o1, 50), (o2, 150)])

    lce_owners = [(o1, 50), (o2, 150)]
    charge = create_charge_with_repartitions(
        db.session, 'Elevator repair', 2000.0, 'extraordinary',
        lce_owners, purpose='Elevator repair', lce_id=lce.id,
    )
    db.session.commit()

    assert charge.limited_common_element_id == lce.id
    rep_owner_ids = {r.owner_id for r in charge.repartitions}
    assert rep_owner_ids == {o1.id, o2.id}
    assert o3.id not in rep_owner_ids


def test_extraordinary_lce_scope_uses_lce_shares(app, db):
    """LCE-scoped charge amounts must use LCE shares, not general_share."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)  # general_share = 100
    o2 = make_owner(db.session, 'Bob', 'B2', 200)    # general_share = 200

    # LCE shares differ from general shares
    lce = make_lce(db.session, 'Elevator', [(o1, 40), (o2, 60)])

    # Total LCE shares = 100, total = 1000
    # Alice: 40/100 * 1000 = 400
    # Bob:   60/100 * 1000 = 600
    lce_owners = [(o1, 40), (o2, 60)]
    charge = create_charge_with_repartitions(
        db.session, 'Elevator repair', 1000.0, 'extraordinary',
        lce_owners, purpose='Elevator repair', lce_id=lce.id,
    )
    db.session.commit()

    alice_inst = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o1.id,
    ).one()
    bob_inst = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o2.id,
    ).one()

    assert abs(alice_inst.amount - 400.0) < 0.01
    assert abs(bob_inst.amount - 600.0) < 0.01


def test_lce_share_snapshot_differs_from_general_share(app, db):
    """share_snapshot should store LCE shares when LCE-scoped."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)  # general_share = 100

    lce = make_lce(db.session, 'Parking', [(o1, 42)])

    charge = create_charge_with_repartitions(
        db.session, 'Parking fix', 500.0, 'extraordinary',
        [(o1, 42)], purpose='Parking', lce_id=lce.id,
    )
    db.session.commit()

    rep = ChargeRepartition.query.filter_by(
        charge_id=charge.id, owner_id=o1.id
    ).one()
    # Snapshot should be the LCE share (42), not general_share (100)
    assert rep.share_snapshot == 42


def test_lce_share_snapshot_immutable_after_lce_edit(app, db):
    """Modifying an LCE share should not affect existing charge repartitions."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    lce = make_lce(db.session, 'Parking', [(o1, 42)])

    charge = create_charge_with_repartitions(
        db.session, 'Parking fix', 500.0, 'extraordinary',
        [(o1, 42)], purpose='Parking', lce_id=lce.id,
    )
    db.session.commit()

    # Change the LCE share
    lce_share = LCEShare.query.filter_by(element_id=lce.id, owner_id=o1.id).one()
    lce_share.share = 999
    db.session.commit()

    rep = ChargeRepartition.query.filter_by(
        charge_id=charge.id, owner_id=o1.id
    ).one()
    assert rep.share_snapshot == 42


def test_no_repartitions_when_no_owners(app, db):
    """A charge with no owners should create no repartitions."""
    charge = create_charge_with_repartitions(
        db.session, 'Empty charge', 1000.0, 'extraordinary',
        [], purpose='Nothing',
    )
    db.session.commit()

    assert len(charge.repartitions) == 0
    assert PaymentInstallment.query.count() == 0


def test_lce_model_basics(app, db):
    """LimitedCommonElement and LCEShare models work correctly."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    o2 = make_owner(db.session, 'Bob', 'B2', 200)

    lce = make_lce(db.session, 'Elevator', [(o1, 50), (o2, 150)], description='Building A')
    db.session.commit()

    loaded = LimitedCommonElement.query.get(lce.id)
    assert loaded.name == 'Elevator'
    assert loaded.description == 'Building A'
    assert len(loaded.shares) == 2
    assert {s.owner_id for s in loaded.shares} == {o1.id, o2.id}
