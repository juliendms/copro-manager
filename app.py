# app.py
import os

from flask import Flask, render_template
from models import db
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
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
