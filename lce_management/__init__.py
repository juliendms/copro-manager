from flask import Blueprint

lce_bp = Blueprint('lce', __name__, template_folder='templates', url_prefix='/elements')

from . import routes
