from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, DateTime
from sqlalchemy.ext.associationproxy import association_proxy

db = SQLAlchemy()

class ChargeRepartition(db.Model):
    __tablename__ = 'charge_repartition'
    charge_id = db.Column(db.Integer, db.ForeignKey('charge.id'), primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('owner.id'), primary_key=True)

    charge = db.relationship('Charge', back_populates='repartitions')
    owner = db.relationship('Owner', back_populates='repartitions')

    installments = db.relationship('PaymentInstallment', back_populates='charge_repartition', cascade="all, delete-orphan", lazy='dynamic')


class Owner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lot_number = db.Column(db.String(10), unique=True, nullable=False)
    share = db.Column(db.Integer, nullable=False) # Changed to Integer

    # Establish a relationship with OwnerEmail
    emails = db.relationship('OwnerEmail', backref='owner', lazy=True, cascade="all, delete-orphan")
    repartitions = db.relationship('ChargeRepartition', back_populates='owner', lazy='dynamic', cascade="all, delete-orphan")
    
    charges = association_proxy('repartitions', 'charge')

    def __repr__(self):
        return f'<Owner {self.name}>'

class OwnerEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('owner.id'), nullable=False)

    def __repr__(self):
        return f'<OwnerEmail {self.email} for Owner ID: {self.owner_id}>'

class Charge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50), nullable=False, default='common') # 'common' or 'extraordinary'
    payment_schedule = db.Column(db.String(50), nullable=False, default='one_time') # 'one_time' or 'quarterly'
    year = db.Column(db.Integer, nullable=True) # Made nullable
    purpose = db.Column(db.String(200), nullable=True) # New field for extraordinary charges
    voting_date = db.Column(Date, nullable=True)
    date_created = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    repartitions = db.relationship('ChargeRepartition', back_populates='charge', cascade="all, delete-orphan")
    owners = association_proxy('repartitions', 'owner')

    @property
    def status(self):
        if not self.repartitions:
            return 'New'

        all_installments = [
            inst for rep in self.repartitions for inst in rep.installments
        ]

        if not all_installments:
            return 'New'

        installment_statuses = {inst.status for inst in all_installments}

        if installment_statuses == {'Paid'}:
            return 'Closed'
        if installment_statuses == {'Draft'}:
            return 'New'
        return 'Ongoing'

    def __repr__(self):
        return f'<Charge {self.description} ({self.type})>'


class PaymentInstallment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    charge_repartition_charge_id = db.Column(db.Integer, nullable=False)
    charge_repartition_owner_id = db.Column(db.Integer, nullable=False)
    
    quarter = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Float, nullable=False)
    
    email_sent_date = db.Column(db.DateTime, nullable=True)
    paid_date = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.ForeignKeyConstraint(['charge_repartition_charge_id', 'charge_repartition_owner_id'],
                                            ['charge_repartition.charge_id', 'charge_repartition.owner_id']),
                      {})

    charge_repartition = db.relationship('ChargeRepartition', back_populates='installments')

    @property
    def status(self):
        if self.paid_date:
            return 'Paid'
        elif self.email_sent_date:
            return 'Sent'
        else:
            return 'Draft'
