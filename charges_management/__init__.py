from flask import Blueprint

charges_bp = Blueprint('charges', __name__, template_folder='templates', url_prefix='/charges')

from . import routes
