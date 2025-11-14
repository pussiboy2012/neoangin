import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..utils import PRODUCTS, USERS, ORDERS, STOCKS, read_json, write_json, list_json, gen_id, login_required, \
    get_user_by_username
from pathlib import Path
from datetime import datetime
import re
import hashlib
import phonenumbers
from email_validator import validate_email, EmailNotValidError

bp = Blueprint("buyer", __name__)


def validate_inn(inn):
    """Валидация ИНН"""
    if not inn or not inn.isdigit():
        return False

    inn = inn.strip()

    if len(inn) == 10:
        # Валидация ИНН юридического лица
        coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        total = sum(int(inn[i]) * coefficients[i] for i in range(9))
        control = (total % 11) % 10
        return control == int(inn[9])
    elif len(inn) == 12:
        # Валидация ИНН индивидуального предпринимателя
        coefficients1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        coefficients2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]

        total1 = sum(int(inn[i]) * coefficients1[i] for i in range(10))
        total2 = sum(int(inn[i]) * coefficients2[i] for i in range(11))

        control1 = (total1 % 11) % 10
        control2 = (total2 % 11) % 10

        return control1 == int(inn[10]) and control2 == int(inn[11])

    return

# Домены, которые разрешены для регистрации
ALLOWED_DOMAINS = ['company.com', 'organization.ru', 'firma.org']  # замените на ваши домены

# Загрузка токена из .env
DADATA_TOKEN = os.environ.get("DADATA_TOKEN")


@bp.route("/verify_inn", methods=["POST"])
def verify_inn():
    """Проверка ИНН через DaData API"""
    inn = request.json.get('inn', '').strip()

    if not inn or not inn.isdigit() or len(inn) not in [10, 12]:
        return jsonify({'success': False, 'error': 'Неверный формат ИНН'})

    try:
        # Запрос к DaData API
        response = requests.post(
            'https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Token {DADATA_TOKEN}'
            },
            json={'query': inn},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('suggestions'):
                company = data['suggestions'][0]
                return jsonify({
                    'success': True,
                    'company_name': company.get('value', ''),
                    'full_name': company.get('data', {}).get('name', {}).get('full', ''),
                    'inn': company.get('data', {}).get('inn', ''),
                    'kpp': company.get('data', {}).get('kpp', ''),
                    'address': company.get('data', {}).get('address', {}).get('value', '')
                })
            else:
                return jsonify({'success': False, 'error': 'Компания с таким ИНН не найдена'})
        else:
            return jsonify({'success': False, 'error': 'Ошибка сервиса проверки ИНН'})

    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': 'Ошибка подключения к сервису'})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'})

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()


def validate_corporate_email(email):
    """Проверка корпоративной почты"""
    try:
        # Валидация email
        valid = validate_email(email)
        email = valid.email

        # Проверка домена
        domain = email.split('@')[1]
        if domain not in ALLOWED_DOMAINS:
            return False, f"Разрешены только корпоративные почты доменов: {', '.join(ALLOWED_DOMAINS)}"

        return True, email
    except EmailNotValidError as e:
        return False, str(e)


def validate_phone_number(phone):
    """Валидация номера телефона"""
    try:
        parsed_number = phonenumbers.parse(phone, "RU")
        if phonenumbers.is_valid_number(parsed_number):
            return True, phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        else:
            return False, "Неверный номер телефона"
    except:
        return False, "Неверный формат номера телефона"

bp = Blueprint("buyer", __name__)


@bp.route("/")
def index():
    # Получаем продукты для главной страницы
    products = list_json(PRODUCTS)
    # Берем только первые 6 товаров для показа на главной
    featured_products = products[:6] if products else []

    return render_template("index.html", products=featured_products)

# ---- auth ----
@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Получаем данные из формы
        full_name = request.form["full_name"].strip()
        inn = request.form["inn"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # Валидации
        errors = []

        # Проверка ИНН
        if not validate_inn(inn):
            errors.append("Неверный формат ИНН")

        # Остальные валидации...
        if len(full_name) < 2:
            errors.append("ФИО должно содержать минимум 2 символа")

        # Проверка email, телефона, пароля...
        is_valid_email, email_error = validate_corporate_email(email)
        if not is_valid_email:
            errors.append(email_error)

        is_valid_phone, phone_error = validate_phone_number(phone)
        if not is_valid_phone:
            errors.append(phone_error)

        if len(password) < 8:
            errors.append("Пароль должен содержать минимум 8 символов")
        if password != confirm_password:
            errors.append("Пароли не совпадают")

        # Проверка существующего пользователя
        if get_user_by_username(email):
            errors.append("Пользователь с таким email уже существует")

        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for("buyer.register"))

        # Получаем название компании из DaData
        company_name = get_company_name_by_inn(inn)

        # Создание пользователя
        user = {
            "id": gen_id("u_"),
            "username": email,
            "email": email,
            "full_name": full_name,
            "company_name": company_name,  # Сохраняем название компании
            "inn": inn,
            "phone": phone,
            "password": hash_password(password),
            "role": "buyer",
            "created_at": datetime.utcnow().isoformat(),
            "company_verified": bool(company_name)  # Верифицируем если получили название
        }

        write_json(Path(USERS) / f"{user['id']}.json", user)
        flash("Регистрация успешна! Компания зарегистрирована.")
        return redirect(url_for("buyer.login"))

    return render_template("register.html")


def get_company_name_by_inn(inn):
    """Получает название компании по ИНН из DaData"""
    if not DADATA_TOKEN:
        return None

    try:
        response = requests.post(
            'https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': f'Token {DADATA_TOKEN}'
            },
            json={'query': inn},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('suggestions'):
                company = data['suggestions'][0]
                return company.get('value', '')  # Возвращаем название компании
    except:
        pass  # В случае ошибки возвращаем None

    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["username"].strip().lower()
        password = request.form["password"]

        user = get_user_by_username(email)
        if not user or user.get("password") != hash_password(password):
            flash("Неверные учётные данные")
            return redirect(url_for("buyer.login"))

        # Обновляем сессию со всеми данными пользователя
        session["user"] = {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "phone": user.get("phone", ""),
            "inn": user.get("inn", ""),  # Добавляем ИНН
            "role": user["role"],
            "company_name": user["company_name"],
            "company_verified": user.get("company_verified", False)
        }
        session.setdefault("cart", {})
        flash("Вход выполнен")
        return redirect(url_for("buyer.index"))

    return render_template("login.html")

@bp.route("/logout")
def logout():
    session.clear()
    flash("Выход")
    return redirect(url_for("buyer.index"))

# ---- catalog ----
@bp.route("/catalog")
def catalog():
    category = request.args.get('category', '')
    products = list_json(PRODUCTS)

    # Фильтрация по категории
    if category:
        products = [p for p in products if p.get('category') == category]

    stocks = {p.get("id"): read_json(Path(STOCKS) / f"{p.get('id')}.json") for p in products}
    return render_template("catalog.html", products=products, stocks=stocks, current_category=category)
@bp.route("/product/<product_id>")
def product_detail(product_id):
    p = read_json(Path(PRODUCTS) / f"{product_id}.json")
    stock = read_json(Path(STOCKS) / f"{product_id}.json") or {"qty": 0}
    if not p:
        flash("Товар не найден")
        return redirect(url_for("buyer.catalog"))
    return render_template("product.html", product=p, stock=stock)

# ---- cart ----
@bp.route("/cart")
def cart():
    cart = session.get("cart", {})
    items = []
    total = 0
    for pid, qty in cart.items():
        prod = read_json(Path(PRODUCTS) / f"{pid}.json")
        if prod:
            items.append({"product": prod, "qty": qty, "sum": prod.get("price", 0)*qty})
            total += prod.get("price",0)*qty
    return render_template("cart.html", items=items, total=total)

@bp.route("/cart/add/<product_id>", methods=["POST","GET"])
def add_to_cart(product_id):
    qty = int(request.form.get("qty", 1)) if request.method=="POST" else 1
    cart = session.setdefault("cart", {})
    cart[product_id] = cart.get(product_id,0) + qty
    session["cart"] = cart
    flash("Добавлено в корзину")
    return redirect(url_for("buyer.cart"))

@bp.route("/cart/remove/<product_id>")
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    if product_id in cart:
        cart.pop(product_id)
        session["cart"] = cart
    return redirect(url_for("buyer.cart"))

# ---- order ----
@bp.route("/order/create", methods=["GET", "POST"])
@login_required()
def create_order():
    # Инициализируем переменные для GET запроса
    items = []
    total = 0

    if request.method == "POST":
        cart = session.get("cart", {})
        if not cart:
            flash("Корзина пуста")
            return redirect(url_for("buyer.cart"))

        order_id = gen_id("o_")
        items = []
        total = 0

        for pid, qty in cart.items():
            p = read_json(Path(PRODUCTS) / f"{pid}.json")
            price = p.get("price", 0) if p else 0
            items.append({"product_id": pid, "title": p.get("title") if p else "?", "qty": qty, "price": price})
            total += price * qty

        order = {
            "id": order_id,
            "user_id": session["user"]["id"],
            "items": items,
            "total": total,
            "status": "pending_moderation",
            "created_at": datetime.utcnow().isoformat()
        }
        write_json(Path(ORDERS) / f"{order_id}.json", order)

        # Очистка корзины
        session["cart"] = {}
        session.modified = True

        flash("Заказ отправлен на модерацию")
        return redirect(url_for("buyer.orders"))

    # GET запрос - показываем страницу подтверждения
    # Для GET запроса нужно получить данные из корзины
    cart = session.get("cart", {})
    items = []
    total = 0

    for pid, qty in cart.items():
        p = read_json(Path(PRODUCTS) / f"{pid}.json")
        if p:
            price = p.get("price", 0)
            items.append({
                "product_id": pid,
                "title": p.get("title", "Неизвестный товар"),
                "qty": qty,
                "price": price,
                "sum": price * qty
            })
            total += price * qty

    return render_template("order_create.html", items=items, total=total)

@bp.route('/update_cart', methods=['POST'])
def update_cart():
    product_id = request.form.get('product_id')
    change = int(request.form.get('change', 0))

    cart = session.get('cart', {})

    if product_id in cart:
        new_qty = cart[product_id] + change
        if new_qty > 0:
            cart[product_id] = new_qty
        else:
            # Если количество стало 0 или меньше, удаляем товар
            cart.pop(product_id, None)

        session['cart'] = cart
        session.modified = True

    return redirect(url_for('buyer.cart'))

@bp.route("/orders")
@login_required()
def orders():
    all_orders = list_json(ORDERS)
    user_orders = [o for o in all_orders if o.get("user_id")==session["user"]["id"]]
    return render_template("orders.html", orders=user_orders)

# ---- profile ----
@bp.route("/profile")
@login_required()
def profile():
    return render_template("profile.html", user=session.get("user"))


@bp.route("/stock")
def stock():
    products = list_json(PRODUCTS)

    # Получаем остатки для всех товаров
    stocks = {}
    for product in products:
        product_id = product.get("id")
        stock_file = Path(STOCKS) / f"{product_id}.json"
        if stock_file.exists():
            stock_data = read_json(stock_file)
            stocks[product_id] = stock_data
        else:
            stocks[product_id] = {"qty": 0}

    # Фильтруем только товары с остатком > 0
    in_stock_products = []
    for product in products:
        product_id = product.get("id")
        stock_qty = stocks.get(product_id, {}).get("qty", 0)
        if stock_qty > 0:
            in_stock_products.append(product)

    return render_template("stock.html", products=in_stock_products, stocks=stocks)