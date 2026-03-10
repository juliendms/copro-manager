"""Priority 1 — Common charge workflow tests.

These tests protect the working quarterly common charge flow
from regressions during the LCE refactor (ADR-002).
"""
from datetime import datetime, timezone

from models import Charge, ChargeRepartition, PaymentInstallment, Owner
from tests.conftest import make_owner, create_charge_with_repartitions


def test_common_charge_creates_repartitions_for_all_owners(app, db):
    """A common charge should create one ChargeRepartition per owner."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    o2 = make_owner(db.session, 'Bob', 'B2', 200)
    o3 = make_owner(db.session, 'Carol', 'C3', 300)

    owners = [(o1, o1.general_share), (o2, o2.general_share), (o3, o3.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Maintenance 2026', 6000.0, 'common',
        owners, year=2026,
    )
    db.session.commit()

    assert len(charge.repartitions) == 3
    rep_owner_ids = {r.owner_id for r in charge.repartitions}
    assert rep_owner_ids == {o1.id, o2.id, o3.id}


def test_common_charge_creates_four_quarterly_installments_per_owner(app, db):
    """Each owner should get 4 installments (Q1–Q4) for a common charge."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)

    owners = [(o1, o1.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Maintenance 2026', 4000.0, 'common',
        owners, year=2026,
    )
    db.session.commit()

    installments = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o1.id,
    ).order_by(PaymentInstallment.quarter).all()

    assert len(installments) == 4
    assert [i.quarter for i in installments] == [1, 2, 3, 4]


def test_common_charge_amounts_proportional_to_shares(app, db):
    """Installment amounts must be proportional to owner shares."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    o2 = make_owner(db.session, 'Bob', 'B2', 300)

    # Total shares = 400, total_amount = 4000
    # Alice: 100/400 * 4000 = 1000 yearly → 250/quarter
    # Bob:   300/400 * 4000 = 3000 yearly → 750/quarter
    owners = [(o1, o1.general_share), (o2, o2.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Maintenance 2026', 4000.0, 'common',
        owners, year=2026,
    )
    db.session.commit()

    alice_installments = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o1.id,
    ).all()

    bob_installments = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id,
        charge_repartition_owner_id=o2.id,
    ).all()

    for inst in alice_installments:
        assert abs(inst.amount - 250.0) < 0.01

    for inst in bob_installments:
        assert abs(inst.amount - 750.0) < 0.01


def test_share_snapshot_is_stored(app, db):
    """ChargeRepartition must store the share_snapshot used at creation."""
    o1 = make_owner(db.session, 'Alice', 'A1', 150)
    owners = [(o1, o1.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Maintenance 2026', 1000.0, 'common',
        owners, year=2026,
    )
    db.session.commit()

    rep = ChargeRepartition.query.filter_by(
        charge_id=charge.id, owner_id=o1.id
    ).one()
    assert rep.share_snapshot == 150


def test_share_snapshot_immutable_after_owner_edit(app, db):
    """Changing an owner's general_share must not affect existing repartitions."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    owners = [(o1, o1.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Maintenance 2026', 1000.0, 'common',
        owners, year=2026,
    )
    db.session.commit()

    # Now change Alice's share
    o1.general_share = 999
    db.session.commit()

    rep = ChargeRepartition.query.filter_by(
        charge_id=charge.id, owner_id=o1.id
    ).one()
    # Snapshot should still be 100
    assert rep.share_snapshot == 100


def test_common_charge_always_has_null_lce(app, db):
    """Common charges must always have limited_common_element_id = NULL."""
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    owners = [(o1, o1.general_share)]
    charge = create_charge_with_repartitions(
        db.session, 'Maintenance 2026', 1000.0, 'common',
        owners, year=2026,
    )
    db.session.commit()

    assert charge.limited_common_element_id is None
    assert charge.type == 'common'
    assert charge.payment_schedule == 'quarterly'
