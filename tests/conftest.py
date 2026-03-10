import os
import pytest
from models import db as _db, Owner, OwnerEmail, Charge, ChargeRepartition, PaymentInstallment, LimitedCommonElement, LCEShare


@pytest.fixture()
def app():
    # Import here to avoid side effects at module level
    os.environ.setdefault('SECRET_KEY', 'test-secret')
    from app import app as flask_app

    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SERVER_NAME': 'localhost',
    })

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture()
def client(app):
    return app.test_client()


# --- Seed helpers ---

def make_owner(db_session, name, lot_number, general_share, emails=None):
    owner = Owner(name=name, lot_number=lot_number, general_share=general_share)
    db_session.add(owner)
    db_session.flush()
    if emails:
        for email in emails:
            db_session.add(OwnerEmail(email=email, owner=owner))
    db_session.flush()
    return owner


def make_lce(db_session, name, owner_shares, description=None):
    """Create an LCE with owner shares.

    owner_shares: list of (Owner, share_value) tuples
    """
    lce = LimitedCommonElement(name=name, description=description)
    db_session.add(lce)
    db_session.flush()
    for owner, share in owner_shares:
        db_session.add(LCEShare(element_id=lce.id, owner_id=owner.id, share=share))
    db_session.flush()
    return lce


def create_charge_with_repartitions(db_session, description, total_amount, charge_type,
                                     owners_and_shares, year=None, purpose=None,
                                     voting_date=None, lce_id=None):
    """Create a charge and auto-populate repartitions + installments.

    This mirrors the logic that the routes will use.
    owners_and_shares: list of (Owner, share_value) tuples
    """
    payment_schedule = 'quarterly' if charge_type == 'common' else 'one_time'

    charge = Charge(
        description=description,
        total_amount=total_amount,
        type=charge_type,
        payment_schedule=payment_schedule,
        year=year,
        purpose=purpose,
        voting_date=voting_date,
        limited_common_element_id=lce_id,
    )
    db_session.add(charge)
    db_session.flush()

    total_shares = sum(s for _, s in owners_and_shares)

    for owner, share in owners_and_shares:
        rep = ChargeRepartition(
            charge_id=charge.id,
            owner_id=owner.id,
            share_snapshot=share,
        )
        db_session.add(rep)
        db_session.flush()

        owner_amount = (share / total_shares) * total_amount if total_shares > 0 else 0

        if payment_schedule == 'quarterly':
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

    db_session.flush()
    return charge
