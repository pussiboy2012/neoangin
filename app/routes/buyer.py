import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..db_helpers import get_all_products, get_all_users, get_all_orders, create_order, get_orders_by_user, get_stock_by_product_id, create_user, verify_user, update_stock, get_user_by_id, get_product_by_id
from ..models import db, Product
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

    return False

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
        elif response.status_code == 403:
            return jsonify({'success': False, 'error': 'Неверный токен доступа к сервису'})
        elif response.status_code == 429:
            return jsonify({'success': False, 'error': 'Превышен лимит запросов к сервису'})
        else:
            return jsonify({'success': False, 'error': f'Ошибка сервиса проверки ИНН: {response.status_code}'})

    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': 'Ошибка подключения к сервису'})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'})


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        inn = request.form.get('inn', '')
        company_name = request.form.get('company_name', '')
        phone = request.form.get('phone', '')

        try:
            user = create_user(email, name, inn, company_name, phone, password, 'buyer')
            if is_ajax:
                return jsonify({'success': True, 'message': 'Регистрация успешна!'})
            else:
                flash('Регистрация успешна!')
                return redirect(url_for('buyer.login'))
        except Exception as e:
            if is_ajax:
                return jsonify({'success': False, 'message': str(e)})
            else:
                flash('Ошибка при регистрации: ' + str(e))

    return render_template('register.html', title="Регистрация")


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        email = request.form.get('email')
        password = request.form.get('password')

        user = verify_user(email, password)
        if user:
            session['user_id'] = user.id_user
            session['user_name'] = user.fullname_user
            session['user_role'] = user.role_user
            session['user'] = {
                'id': user.id_user,
                'name': user.fullname_user,
                'role': user.role_user,
                'email': user.email_user
            }
            if is_ajax:
                return jsonify({'success': True, 'redirect': url_for('buyer.index')})
            else:
                flash('Добро пожаловать, ' + user.fullname_user + '!')
                return redirect(url_for('buyer.index'))
        else:
            if is_ajax:
                return jsonify({'success': False, 'message': 'Неверный email или пароль.'})
            else:
                flash('Неверный email или пароль.')

    return render_template('login.html', title="Авторизация")

@bp.route('/logout')
def logout():
    session.clear()
    flash('Вы успешно вышли из системы.')
    return redirect(url_for('buyer.index'))

@bp.route('/profile')
def profile():
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    user = get_user_by_id(session['user']['id'])
    return render_template('profile.html', title="Профиль", user=user)


@bp.route("/catalog")
def catalog():
    products = get_all_products()
    return render_template("catalog.html", products=products)


@bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = get_product_by_id(product_id)
    if not product:
        flash('Товар не найден.')
        return redirect(url_for('buyer.catalog'))

    stock = get_stock_by_product_id(product_id)
    stock_qty = stock.count_stock if stock else 0

    return render_template("product.html", product=product, stock={"qty": stock_qty})


@bp.route("/cart")
def cart():
    cart = session.get("cart", {})
    items = []
    total = 0

    for pid, qty in cart.items():
        try:
            product_id = int(pid)
            product = get_product_by_id(product_id)
            if product:
                price = float(product.price_product)
                items.append({
                    "product_id": pid,
                    "title": product.title_product,
                    "qty": qty,
                    "price": price,
                    "sum": price * qty
                })
                total += price * qty
        except (ValueError, TypeError):
            # Skip invalid product IDs
            continue

    return render_template("cart.html", items=items, total=total)


@bp.route('/create_order', methods=['POST'])
def create_order_route():
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    cart = session.get("cart", {})
    if not cart:
        flash('Корзина пуста.')
        return redirect(url_for('buyer.cart'))

    # Создаем заказ
    order_id = create_order(session['user']['id'], cart)
    if order_id:
        session['cart'] = {}
        flash('Заказ создан успешно!')
        return redirect(url_for("buyer.orders"))
    else:
        flash('Ошибка при создании заказа.')
        return redirect(url_for('buyer.cart'))


@bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    qty = int(request.form.get('qty', 1))

    if not product_id:
        flash('Неверный товар.')
        return redirect(url_for('buyer.catalog'))

    cart = session.get('cart', {})
    cart[product_id] = cart.get(product_id, 0) + qty
    session['cart'] = cart
    session.modified = True

    flash('Товар добавлен в корзину!')
    return redirect(url_for('buyer.cart'))


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
def orders():
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    user_orders = get_orders_by_user(session['user']['id'])
    return render_template("orders.html", orders=user_orders)


@bp.route("/stock")
def stock():
    from sqlalchemy import text

    # Получаем данные из представления product_stock_series
    stock_series = db.session.execute(text("""
        SELECT nomenclature_ral, series_info, remaining_quantity
        FROM product_stock_series
        ORDER BY nomenclature_ral, series_info
    """)).fetchall()

    # Получаем все продукты для сопоставления названий
    products = get_all_products()
    product_names = {p.nomenclature_product: p.title_product for p in products}
    product_ids = {p.nomenclature_product: p.id_product for p in products}

    # Подготавливаем данные для шаблона
    stock_data = []
    for series in stock_series:
        product_name = product_names.get(series.nomenclature_ral, series.nomenclature_ral)
        product_id = product_ids.get(series.nomenclature_ral, series.nomenclature_ral)
        if product_id is not None:
            stock_data.append({
                'product_name': product_name,
                'nomenclature_ral': series.nomenclature_ral,
                'series_info': series.series_info,
                'remaining_quantity': series.remaining_quantity,
                'product_id': product_id
            })

    return render_template("stock.html", stock_data=stock_data)
