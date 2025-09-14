# app.py
import os

from flask import Flask, render_template, url_for
from models import db, Charge, Owner, ChargeRepartition, PaymentInstallment
from sqlalchemy.orm import joinedload
from dotenv import load_dotenv

from owner_management import owner_bp # Import the blueprint
from charges_management import charges_bp # Import the charges blueprint

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

app.register_blueprint(owner_bp) # Register the blueprint
app.register_blueprint(charges_bp) # Register the charges blueprint

@app.route('/initial_db_setup')
def initial_db_setup():
    with app.app_context():
        db.create_all()
    return "Database tables created!"

@app.route('/')
def index():
    charges = Charge.query.options(
        joinedload(Charge.repartitions)
        .joinedload(ChargeRepartition.owner)
    ).all()

    dashboard_charges = []
    for charge in charges:
        if charge.status == 'Ongoing':
            if charge.type == 'extraordinary':
                installments = (
                    PaymentInstallment.query.join(ChargeRepartition)
                    .filter(ChargeRepartition.charge_id == charge.id)
                    .options(
                        joinedload(PaymentInstallment.charge_repartition)
                        .joinedload(ChargeRepartition.owner)
                        .joinedload(Owner.emails)
                    )
                    .all()
                )
                dashboard_charges.append({
                    'charge': charge,
                    'installments': installments,
                    'quarter': None
                })
            elif charge.type == 'common':
                # Find the default quarter (first with unpaid installments)
                all_installments = (
                    PaymentInstallment.query.join(ChargeRepartition)
                    .filter(ChargeRepartition.charge_id == charge.id)
                    .order_by(PaymentInstallment.quarter)
                    .all()
                )
                
                quarter_completion = {}
                for i in range(1, 5):
                    quarter_installments = [inst for inst in all_installments if inst.quarter == i]
                    if quarter_installments:
                        quarter_completion[i] = all(inst.status == 'Paid' for inst in quarter_installments)
                    else:
                        quarter_completion[i] = False
                
                default_quarter = None
                for i in range(1, 5):
                    if not quarter_completion.get(i, True):
                        default_quarter = i
                        break
                
                if default_quarter:
                    quarter_installments = [inst for inst in all_installments if inst.quarter == default_quarter]
                    dashboard_charges.append({
                        'charge': charge,
                        'installments': quarter_installments,
                        'quarter': default_quarter
                    })

    return render_template('index.html', dashboard_charges=dashboard_charges)

@app.route('/fragments/flash')
def flash_fragment():
    # Render only the flash messages content; base listens for flash-refresh
    return render_template('partials/flash_messages.html')


if __name__ == '__main__':
    app.run(debug=True)
