import os
from flask import Flask
from .utils import ensure_data_dirs

def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="templates")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

    ensure_data_dirs()

    # register blueprints
    from .routes.buyer import bp as buyer_bp
    from .routes.manager import bp as manager_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(buyer_bp)
    app.register_blueprint(manager_bp, url_prefix="/manager")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app
