import os
import json
from functools import wraps
from flask import session, redirect, url_for, flash
from pathlib import Path
from uuid import uuid4
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PRODUCTS = DATA_DIR / "products"
USERS = DATA_DIR / "users"
ORDERS = DATA_DIR / "orders"
STOCKS = DATA_DIR / "stocks"
ANALYTICS = DATA_DIR / "analytics"

def ensure_data_dirs():
    for d in [DATA_DIR, PRODUCTS, USERS, ORDERS, STOCKS, ANALYTICS]:
        d.mkdir(parents=True, exist_ok=True)
    # create default admin if not exists
    admin_file = USERS / "admin.json"
    if not admin_file.exists():
        admin = {
            "id": "admin",
            "username": "admin",
            "password": "admin",  # simple for demo
            "role": "admin",
            "created_at": datetime.utcnow().isoformat()
        }
        admin_file.write_text(json.dumps(admin, ensure_ascii=False, indent=2))

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