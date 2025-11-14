import json
import logging
from functools import wraps
from flask import session, redirect, url_for, flash
from pathlib import Path
from uuid import uuid4
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS = DATA_DIR / "products"
USERS = DATA_DIR / "users"
ORDERS = DATA_DIR / "orders"
STOCKS = DATA_DIR / "stocks"
ANALYTICS = DATA_DIR / "analytics"

CHATS_DIR = Path("data/chats")


def ensure_chats_dir():
    """Создает директорию для чатов"""
    CHATS_DIR.mkdir(parents=True, exist_ok=True)


def get_user_chat_file(user_id):
    """Возвращает путь к файлу чата пользователя"""
    return CHATS_DIR / f"{user_id}.json"


def create_chat(user_id, user_name):
    """Создает новый чат для пользователя"""
    chat_file = get_user_chat_file(user_id)
    chat_data = {
        "user_id": user_id,
        "user_name": user_name,
        "created_at": datetime.utcnow().isoformat(),
        "messages": [],
        "bot_enabled": True,
        "assigned_manager": None,
        "status": "active"
    }
    write_json(chat_file, chat_data)
    return chat_data


def get_chat(user_id):
    """Получает чат пользователя"""
    chat_file = get_user_chat_file(user_id)
    if chat_file.exists():
        return read_json(chat_file)
    return None


def add_message_to_chat(user_id, role, content, message_type="text"):
    """Добавляет сообщение в чат"""
    chat = get_chat(user_id)
    if not chat:
        return None

    message = {
        "id": gen_id("msg_"),
        "role": role,  # "user", "assistant", "manager"
        "content": content,
        "type": message_type,
        "timestamp": datetime.utcnow().isoformat(),
        "sender_name": get_sender_name(role, user_id)
    }

    chat["messages"].append(message)
    chat["last_activity"] = datetime.utcnow().isoformat()

    write_json(get_user_chat_file(user_id), chat)
    return message


def get_sender_name(role, user_id):
    """Возвращает имя отправителя"""
    if role == "user":
        user_data = read_json(Path(USERS) / f"{user_id}.json")
        return user_data.get("full_name", "Покупатель")
    elif role == "assistant":
        return "AI Ассистент"
    elif role == "manager":
        return "Менеджер"
    return "Неизвестный"


def get_all_chats():
    """Получает все чаты"""
    ensure_chats_dir()
    chats = []
    for chat_file in CHATS_DIR.glob("*.json"):
        chat_data = read_json(chat_file)
        if chat_data:
            # Добавляем информацию о последнем сообщении
            last_message = chat_data["messages"][-1] if chat_data["messages"] else None
            chat_data["last_message"] = last_message
            chat_data["unread_count"] = len(
                [m for m in chat_data["messages"] if m.get("role") == "user" and not m.get("read")])
            chats.append(chat_data)

    # Сортируем по последней активности
    chats.sort(key=lambda x: x.get("last_activity", x["created_at"]), reverse=True)
    return chats


def toggle_bot_for_chat(user_id, enabled):
    """Включает/выключает бота для чата"""
    chat = get_chat(user_id)
    if chat:
        chat["bot_enabled"] = enabled
        write_json(get_user_chat_file(user_id), chat)
        return True
    return False


def assign_manager_to_chat(user_id, manager_id):
    """Назначает менеджера на чат"""
    chat = get_chat(user_id)
    if chat:
        chat["assigned_manager"] = manager_id
        chat["bot_enabled"] = False  # При назначении менеджера выключаем бота
        write_json(get_user_chat_file(user_id), chat)
        return True
    return False

def ensure_data_dirs():
    """
    Создает необходимые директории и файлы для работы приложения.
    Обрабатывает возможные ошибки и логирует процесс.
    """
    try:
        # Список директорий для создания
        directories = [DATA_DIR, PRODUCTS, USERS, ORDERS, STOCKS, ANALYTICS]

        # Создаем директории
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"Директория {directory} проверена/создана")
            except PermissionError:
                logger.error(f"Ошибка прав доступа при создании директории {directory}")
                raise
            except OSError as e:
                logger.error(f"Ошибка OS при создании директории {directory}: {e}")
                raise

        # Создаем администратора по умолчанию
        create_default_admin()

        logger.info("Все директории и файлы успешно инициализированы")

    except Exception as e:
        logger.error(f"Критическая ошибка при инициализации данных: {e}")
        raise


def create_default_admin():
    """
    Создает администратора по умолчанию, если он не существует.
    """
    admin_file = USERS / "admin.json"

    try:
        # Проверяем существование файла
        if not admin_file.exists():
            logger.info("Создание администратора по умолчанию...")

            # Генерируем безопасный пароль по умолчанию
            import hashlib
            import secrets

            # Создаем более безопасный пароль по умолчанию
            default_password = "admin"  # Можно изменить на что-то более сложное
            salt = secrets.token_hex(8)
            hashed_password = hashlib.sha256((default_password + salt).encode()).hexdigest()

            admin_data = {
                "id": "admin",
                "username": "admin",
                "password": hashed_password,
                "salt": salt,
                "role": "admin",
                "email": "admin@company.com",
                "full_name": "Системный администратор",
                "phone": "+70000000000",
                "created_at": datetime.utcnow().isoformat(),
                "is_active": True,
                "last_login": None
            }

            # Записываем с обработкой ошибок
            try:
                with open(admin_file, 'w', encoding='utf-8') as f:
                    json.dump(admin_data, f, ensure_ascii=False, indent=2)

                logger.info("Администратор по умолчанию создан")
                logger.warning(f"ВНИМАНИЕ: Пароль по умолчанию: {default_password} - смените его после первого входа!")

            except IOError as e:
                logger.error(f"Ошибка записи файла администратора: {e}")
                raise

        else:
            # Проверяем целостность существующего файла администратора
            try:
                with open(admin_file, 'r', encoding='utf-8') as f:
                    admin_data = json.load(f)

                # Проверяем обязательные поля
                required_fields = ['id', 'username', 'password', 'role']
                for field in required_fields:
                    if field not in admin_data:
                        logger.warning(f"В файле администратора отсутствует поле {field}")

            except json.JSONDecodeError:
                logger.error("Файл администратора поврежден, создаем заново...")
                admin_file.unlink()  # Удаляем поврежденный файл
                create_default_admin()

    except Exception as e:
        logger.error(f"Ошибка при создании администратора: {e}")
        raise


def verify_data_integrity():
    """
    Дополнительная функция для проверки целостности данных.
    Можно вызывать при запуске приложения.
    """
    try:
        directories = [PRODUCTS, USERS, ORDERS, STOCKS, ANALYTICS]

        for directory in directories:
            if not directory.exists():
                logger.warning(f"Директория {directory} отсутствует, создаем...")
                directory.mkdir(parents=True, exist_ok=True)

        # Проверяем базовые файлы конфигурации
        required_files = [
            USERS / "admin.json"
        ]

        for file_path in required_files:
            if not file_path.exists():
                logger.warning(f"Обязательный файл {file_path} отсутствует")
                # Можно добавить автоматическое создание здесь

        logger.info("Проверка целостности данных завершена")

    except Exception as e:
        logger.error(f"Ошибка при проверке целостности данных: {e}")


# Обновленная функция хеширования пароля для использования в других местах
def hash_password(password, salt=None):
    """
    Хеширует пароль с использованием salt.
    """
    import hashlib
    import secrets

    if salt is None:
        salt = secrets.token_hex(8)

    hashed_password = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed_password, salt


def verify_password(password, hashed_password, salt):
    """
    Проверяет пароль против хеша.
    """
    import hashlib
    test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return test_hash == hashed_password

def read_json(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def list_json(folder):
    folder = Path(folder)
    items = []
    for f in folder.glob("*.json"):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except:
            continue
    return items

def gen_id(prefix=""):
    return prefix + uuid4().hex[:8]

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("buyer.login"))
            if role and session["user"].get("role") != role:
                flash("Нет доступа")
                return redirect(url_for("buyer.index"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def get_user_by_username(username):
    for u in list_json(USERS):
        if u.get("username") == username:
            return u
    return None


def get_all_users():
    """Получить всех пользователей из папки users"""
    users = []
    users_path = Path(USERS)

    if users_path.exists():
        for user_file in users_path.glob("*.json"):
            try:
                user_data = read_json(user_file)
                if user_data and isinstance(user_data, dict):
                    users.append(user_data)
            except Exception as e:
                print(f"Ошибка чтения файла пользователя {user_file}: {e}")

    return users