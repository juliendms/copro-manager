from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date # Import Date type

db = SQLAlchemy()

class Owner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lot_number = db.Column(db.String(10), unique=True, nullable=False)
    share = db.Column(db.Integer, nullable=False) # Changed to Integer

    # Establish a relationship with OwnerEmail
    emails = db.relationship('OwnerEmail', backref='owner', lazy=True, cascade="all, delete-orphan")

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
    year = db.Column(db.Integer, nullable=True) # Made nullable
    purpose = db.Column(db.String(200), nullable=True) # New field for extraordinary charges
    voting_date = db.Column(Date, nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Charge {self.description} ({self.type})>'
