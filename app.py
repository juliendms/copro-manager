# app.py
import os

from flask import Flask, render_template, url_for, g, flash, make_response, current_app
from models import db, Charge, Owner, ChargeRepartition, PaymentInstallment
from sqlalchemy import inspect
from sqlalchemy.orm import joinedload
from dotenv import load_dotenv
from app_utils import no_cache

from owner_management import owner_bp
from charges_management import charges_bp
from lce_management import lce_bp

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

@app.before_request
def check_db_exists():
    database_path = os.path.join(current_app.instance_path, 'app.db')
    g.db_exists = os.path.exists(database_path)

@app.context_processor
def inject_db_exists():
    # Ensure g.db_exists is set, even if it wasn't set by a before_request handler.
    if not hasattr(g, 'db_exists'):
        database_path = os.path.join(current_app.instance_path, 'app.db')
        g.db_exists = os.path.exists(database_path)
    return dict(db_exists=g.db_exists)

app.register_blueprint(owner_bp)
app.register_blueprint(charges_bp)
app.register_blueprint(lce_bp)

@app.route('/initial_db_setup')
def initial_db_setup():
    with app.app_context():
        db.create_all()
    flash("Database tables created successfully!", 'success')
    response = make_response("", 204) # 204 No Content
    response.headers['HX-Redirect'] = url_for('index')
    return response

@app.route('/')
@no_cache
def index():
    dashboard_charges = []
    if g.db_exists:
        charges = Charge.query.options(
            joinedload(Charge.repartitions)
            .joinedload(ChargeRepartition.owner)
        ).all()

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
