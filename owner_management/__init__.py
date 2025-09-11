from flask import Blueprint

owner_bp = Blueprint('owner', __name__, template_folder='templates', url_prefix='/owners')

from . import routes
