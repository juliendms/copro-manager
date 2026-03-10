"""Tests for computed properties on Charge and PaymentInstallment models."""
from datetime import datetime, timezone

from models import Charge, PaymentInstallment, ChargeRepartition
from tests.conftest import make_owner, create_charge_with_repartitions


def test_charge_status_new_when_no_repartitions(app, db):
    charge = Charge(description='Empty', total_amount=100.0, type='common', payment_schedule='quarterly')
    db.session.add(charge)
    db.session.commit()

    assert charge.status == 'New'


def test_charge_status_new_when_all_installments_draft(app, db):
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    charge = create_charge_with_repartitions(
        db.session, 'Test', 1000.0, 'common',
        [(o1, o1.general_share)], year=2026,
    )
    db.session.commit()

    assert charge.status == 'New'


def test_charge_status_ongoing_when_some_sent(app, db):
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    charge = create_charge_with_repartitions(
        db.session, 'Test', 1000.0, 'common',
        [(o1, o1.general_share)], year=2026,
    )
    db.session.commit()

    # Mark first installment as sent
    installments = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id
    ).all()
    installments[0].email_sent_date = datetime.now(timezone.utc)
    db.session.commit()

    assert charge.status == 'Ongoing'


def test_charge_status_ongoing_when_some_paid(app, db):
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    charge = create_charge_with_repartitions(
        db.session, 'Test', 1000.0, 'common',
        [(o1, o1.general_share)], year=2026,
    )
    db.session.commit()

    installments = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id
    ).all()
    installments[0].paid_date = datetime.now(timezone.utc)
    db.session.commit()

    assert charge.status == 'Ongoing'


def test_charge_status_closed_when_all_paid(app, db):
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    charge = create_charge_with_repartitions(
        db.session, 'Test', 1000.0, 'common',
        [(o1, o1.general_share)], year=2026,
    )
    db.session.commit()

    installments = PaymentInstallment.query.filter_by(
        charge_repartition_charge_id=charge.id
    ).all()
    for inst in installments:
        inst.paid_date = datetime.now(timezone.utc)
    db.session.commit()

    assert charge.status == 'Closed'


def test_installment_status_draft(app, db):
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    charge = create_charge_with_repartitions(
        db.session, 'Test', 1000.0, 'extraordinary',
        [(o1, o1.general_share)], purpose='Roof repair',
    )
    db.session.commit()

    inst = PaymentInstallment.query.first()
    assert inst.status == 'Draft'


def test_installment_status_sent(app, db):
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    charge = create_charge_with_repartitions(
        db.session, 'Test', 1000.0, 'extraordinary',
        [(o1, o1.general_share)], purpose='Roof repair',
    )
    db.session.commit()

    inst = PaymentInstallment.query.first()
    inst.email_sent_date = datetime.now(timezone.utc)
    db.session.commit()

    assert inst.status == 'Sent'


def test_installment_status_paid(app, db):
    o1 = make_owner(db.session, 'Alice', 'A1', 100)
    charge = create_charge_with_repartitions(
        db.session, 'Test', 1000.0, 'extraordinary',
        [(o1, o1.general_share)], purpose='Roof repair',
    )
    db.session.commit()

    inst = PaymentInstallment.query.first()
    inst.email_sent_date = datetime.now(timezone.utc)
    inst.paid_date = datetime.now(timezone.utc)
    db.session.commit()

    assert inst.status == 'Paid'
