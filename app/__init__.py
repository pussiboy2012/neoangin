import datetime
import os
from flask import Flask
from .utils import ensure_data_dirs
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy

# Загружаем переменные окружения
load_dotenv()

def create_app():
    app = Flask(__name__, static_folder="../static", template_folder="templates")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:admin@localhost:5432/primetop')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    from .models import db
    db.init_app(app)

    ensure_data_dirs()

    # register blueprints
    from .routes.buyer import bp as buyer_bp
    from .routes.manager import bp as manager_bp
    from .routes.admin import bp as admin_bp
    from .routes.chatbot import bp as chatbot_bp

    app.register_blueprint(buyer_bp)
    app.register_blueprint(manager_bp, url_prefix="/manager")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    # УБЕРИТЕ ПРЕФИКС для обратной совместимости
    app.register_blueprint(chatbot_bp)  # Без url_prefix

    # Добавляем кастомные фильтры
    @app.template_filter('format_chat_time')
    def format_chat_time(value):
        """Форматирует время для чата: ЧЧ:ММ"""
        if not value:
            return ''
        try:
            # Если это ISO строка
            if 'T' in value:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                # Если это уже отформатированное время
                return value
            return dt.strftime('%H:%M')
        except:
            return value

    @app.template_filter('format_chat_date')
    def format_chat_date(value):
        """Форматирует дату для разделителей: ДД.ММ.ГГГГ"""
        if not value:
            return ''
        try:
            if 'T' in value:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.strftime('%d.%m.%Y')
            else:
                return value
        except:
            return value

    return app
