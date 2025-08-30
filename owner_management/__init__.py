from flask import Blueprint

owner_bp = Blueprint('owner_bp', __name__, template_folder='templates', url_prefix='/owners')

from . import routes
