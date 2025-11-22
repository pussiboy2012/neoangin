import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from ..db_helpers import get_all_products, get_all_users, get_all_orders, create_order, get_orders_by_user, get_stock_by_product_id, create_user, verify_user, update_stock, get_user_by_id, get_product_by_id
from ..models import db, Product
from datetime import datetime
from pathlib import Path
from datetime import datetime
import re
import hashlib
import phonenumbers
from email_validator import validate_email, EmailNotValidError
import io

bp = Blueprint("buyer", __name__)


@bp.route("/generate_invoice/<order_id>")
def generate_invoice(order_id):
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    # Извлекаем номер заказа из order_id (формат: order_123)
    try:
        order_number = order_id.split('_')[1]
    except IndexError:
        flash('Неверный формат номера заказа.')
        return redirect(url_for('buyer.orders'))

    # Получаем данные заказа
    from ..models import Order, ProductOrder, StockOrder, Product, Stock, User
    order = Order.query.filter_by(id_order=order_number).first()

    if not order or order.id_user != session['user']['id']:
        flash('Заказ не найден.')
        return redirect(url_for('buyer.orders'))

    # Проверяем, что заказ подтвержден
    if order.status_order != 'approved':
        flash('Счет можно сформировать только для подтвержденных заказов.')
        return redirect(url_for('buyer.orders'))

    # Получаем данные пользователя (покупателя)
    buyer_user = User.query.get(session['user']['id'])

    # Получаем полные данные покупателя через DaData
    buyer_data = get_company_data_by_inn(buyer_user.inn_user)
    if not buyer_data:
        flash('Не удалось получить данные организации через сервис проверки ИНН.')
        return redirect(url_for('buyer.orders'))

    # Получаем данные поставщика (вашей компании) через DaData
    # Замените ИНН вашей компании на реальный
    supplier_inn = "4802024282"  # ИНН из примера счета
    supplier_data = get_company_data_by_inn(supplier_inn)
    if not supplier_data:
        flash('Не удалось получить данные поставщика через сервис проверки ИНН.')
        return redirect(url_for('buyer.orders'))

    # Добавляем банковские реквизиты поставщика (это можно хранить в настройках)
    supplier_data.update({
        'bank_name': 'АО "Стоун банк" Г. МОСКВА',
        'bank_account': '40702810900000002453',
        'correspondent_account': '30101810200000000700',
        'bik': '040525700',
        'phone': '+7 (495) 123-45-67'  # Ваш телефон
    })

    # Формируем данные для счета
    items = []
    total = 0

    # Получаем товары заказа из product-order
    product_orders = ProductOrder.query.filter_by(id_order=order.id_order).all()
    for po in product_orders:
        product = Product.query.get(po.id_product)
        price = float(product.price_product)
        item_total = price * po.count
        total += item_total

        items.append({
            'name': f"{product.title_product}{f' RAL {po.ral}' if po.ral else ''}",
            'quantity': po.count,
            'unit': 'шт.',
            'price': price,
            'total': item_total
        })

    # Получаем товары со склада из stock-order
    stock_orders = StockOrder.query.filter_by(id_order=order.id_order).all()
    for so in stock_orders:
        stock = Stock.query.get(so.id_stock)
        product = Product.query.get(stock.id_product)
        price = float(product.price_product)
        item_total = price * so.count_order
        total += item_total

        items.append({
            'name': f"{product.nomenclature_product}{f' RAL {stock.ral_stock}' if stock.ral_stock else ''} (п.{stock.id_stock})",
            'quantity': so.count_order,
            'unit': 'шт.',
            'price': price,
            'total': item_total
        })

    # Рассчитываем НДС (20%)
    vat_amount = round(total * 0.2, 2)
    total_with_vat = total

    # Генерируем HTML для счета
    invoice_html = render_template(
        "invoice_template.html",
        invoice_number=f"{order_number}/{datetime.now().year}",
        invoice_date=datetime.now().strftime("%d.%m.%Y"),
        supplier=supplier_data,
        buyer=buyer_data,
        basis=f"Заказ №{order_number} от {order.created_at_order.strftime('%d.%m.%Y')}",
        items=items,
        total=total,
        vat_amount=vat_amount,
        total_with_vat=total_with_vat,
        total_words=num2words(total, lang='ru')
    )

    return invoice_html


def get_company_data_by_inn(inn):
    """Получение данных компании по ИНН через DaData API"""
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
                company_data = company.get('data', {})
                address_data = company_data.get('address', {})

                return {
                    'name': company.get('value', ''),
                    'full_name': company_data.get('name', {}).get('full', ''),
                    'inn': company_data.get('inn', ''),
                    'kpp': company_data.get('kpp', ''),
                    'address': address_data.get('value', ''),
                    'postal_code': address_data.get('data', {}).get('postal_code', ''),
                    'city': address_data.get('data', {}).get('city', ''),
                    'address_line': address_data.get('data', {}).get('street_with_type', ''),
                    'house': address_data.get('data', {}).get('house', '')
                }
        return None
    except Exception as e:
        print(f"Ошибка при получении данных компании: {e}")
        return None


def num2words(num, lang='ru'):
    """Упрощенная конвертация числа в пропись"""
    # Для полноценной реализации установите библиотеку: pip install num2words
    try:
        from num2words import num2words as n2w
        return n2w(num, lang='ru')
    except ImportError:
        # Запасной вариант если библиотека не установлена
        integer_part = int(num)
        decimal_part = int(round((num - integer_part) * 100))

        # Простая реализация для основных чисел
        units = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
        teens = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать',
                 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
        tens = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят',
                'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
        hundreds = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот',
                    'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']

        def convert_number(n):
            if n == 0:
                return 'ноль'

            words = []
            if n >= 1000:
                thousands = n // 1000
                if thousands == 1:
                    words.append('одна тысяча')
                elif thousands == 2:
                    words.append('две тысячи')
                elif thousands in [3, 4]:
                    words.append(units[thousands] + ' тысячи')
                else:
                    words.append(convert_number(thousands) + ' тысяч')
                n %= 1000

            if n >= 100:
                words.append(hundreds[n // 100])
                n %= 100

            if n >= 20:
                words.append(tens[n // 10])
                n %= 10

            if n >= 10:
                words.append(teens[n - 10])
                n = 0

            if n > 0:
                words.append(units[n])

            return ' '.join(filter(None, words))

        result = convert_number(integer_part)
        # Склонение рублей
        last_digit = integer_part % 10
        if last_digit == 1 and integer_part % 100 != 11:
            ruble_word = 'рубль'
        elif last_digit in [2, 3, 4] and integer_part % 100 not in [12, 13, 14]:
            ruble_word = 'рубля'
        else:
            ruble_word = 'рублей'

        return f"{result} {ruble_word} {decimal_part:02d} копеек"


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


@bp.route("/settings")
def settings():
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    user = get_user_by_id(session['user']['id'])
    return render_template("buyer_settings.html", title="Настройки", user=user)


@bp.route("/update_company", methods=["POST"])
def update_company():
    """Обновление данных компании пользователя"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Пользователь не авторизован'})

    try:
        data = request.json
        user_id = session['user']['id']

        # Получаем пользователя через существующую функцию
        from ..db_helpers import get_user_by_id
        user = get_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'Пользователь не найден'})

        # Обновляем данные компании
        user.inn_user = data.get('inn', '')
        user.company_name_user = data.get('company_name', '')

        # Добавляем KPP и адрес если они есть в модели
        if hasattr(user, 'kpp_user'):
            user.kpp_user = data.get('kpp', '')
        if hasattr(user, 'address_user'):
            user.address_user = data.get('address', '')

        # Сохраняем изменения
        db.session.commit()

        # Обновляем данные в сессии
        session['user_name'] = user.fullname_user

        return jsonify({
            'success': True,
            'message': 'Данные компании успешно обновлены'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Ошибка при обновлении: {str(e)}'})

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

        # Проверяем, что название компании указано (т.е. ИНН был проверен)
        if not company_name:
            error_msg = 'Пожалуйста, проверьте ИНН перед регистрацией для получения названия компании.'
            if is_ajax:
                return jsonify({'success': False, 'message': error_msg})
            else:
                flash(error_msg)
                return render_template('register.html', title="Регистрация")

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
    stock_items = []
    production_items = []
    total = 0

    for cart_key, item_data in cart.items():
        try:
            product_id = int(item_data.get('product_id', cart_key.split('_')[0]))
            product = get_product_by_id(product_id)
            if product:
                qty = item_data.get('qty', 0)
                ral = item_data.get('ral', '')
                id_stock = item_data.get('id_stock')
                price = float(product.price_product)
                # For stock items with RAL, show nomenclature with RAL
                if ral:
                    title = f"{product.nomenclature_product} RAL {ral}"
                else:
                    title = product.title_product
                # Add stock info if available
                stock_info = ""
                if id_stock:
                    from ..models import Stock
                    stock = Stock.query.get(id_stock)
                    if stock:
                        stock_info = f"п.{stock.id_stock} от {stock.date_stock.strftime('%d.%m.%Y')}"
                item = {
                    "product": product,
                    "product_id": cart_key,
                    "title": title,
                    "qty": qty,
                    "ral": ral,
                    "stock_info": stock_info,
                    "price": price,
                    "sum": price * qty
                }
                if id_stock:
                    stock_items.append(item)
                else:
                    production_items.append(item)
                total += price * qty
        except (ValueError, TypeError):
            # Skip invalid product IDs
            continue

    return render_template("cart.html", stock_items=stock_items, production_items=production_items, total=total)


@bp.route('/create_order', methods=['POST'])
def create_order_route():
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    cart = session.get("cart", {})
    if not cart:
        flash('Корзина пуста.')
        return redirect(url_for('buyer.cart'))

    # Создаем заказ на доставку
    order_id = create_order(session['user']['id'], cart, status='pending_moderation')
    if order_id:
        session['cart'] = {}
        flash('Заказ на доставку создан успешно!')
        return redirect(url_for("buyer.orders"))
    else:
        flash('Ошибка при создании заказа.')
        return redirect(url_for('buyer.cart'))


@bp.route('/create_production_order', methods=['POST'])
def create_production_order():
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    product_id = request.form.get('product_id')
    qty = int(request.form.get('qty', 1))

    if not product_id:
        flash('Неверный товар.')
        return redirect(url_for('buyer.catalog'))

    # Создаем заказ на производство
    items = {product_id: {'qty': qty, 'ral': ''}}  # Для производства RAL не нужен
    order_id = create_order(session['user']['id'], items, status='pending_moderation')
    if order_id:
        flash('Заказ на производство создан успешно!')
        return redirect(url_for("buyer.orders"))
    else:
        flash('Ошибка при создании заказа на производство.')
        return redirect(url_for('buyer.product_detail', product_id=product_id))


@bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    qty = int(request.form.get('qty', 1))
    ral = request.form.get('ral', '')
    id_stock = request.form.get('id_stock')

    if not product_id:
        flash('Неверный товар.')
        return redirect(url_for('buyer.catalog'))

    cart = session.get('cart', {})
    cart_key = f"{product_id}_{ral}_{id_stock}" if id_stock else (f"{product_id}_{ral}" if ral else product_id)

    if cart_key not in cart:
        cart[cart_key] = {'qty': 0, 'ral': ral, 'product_id': product_id, 'id_stock': id_stock}
    cart[cart_key]['qty'] += qty
    session['cart'] = cart
    session.modified = True

    flash('Товар добавлен в корзину!')
    return redirect(url_for('buyer.cart'))


@bp.route('/update_cart', methods=['POST'])
def update_cart():
    cart_key = request.form.get('product_id')
    change = int(request.form.get('change', 0))

    cart = session.get('cart', {})

    if cart_key in cart:
        new_qty = cart[cart_key]['qty'] + change
        if new_qty > 0:
            cart[cart_key]['qty'] = new_qty
        else:
            # Если количество стало 0 или меньше, удаляем товар
            cart.pop(cart_key, None)

        session['cart'] = cart
        session.modified = True

    return redirect(url_for('buyer.cart'))


@bp.route('/remove_from_cart/<cart_key>')
def remove_from_cart(cart_key):
    cart = session.get('cart', {})
    if cart_key in cart:
        cart.pop(cart_key, None)
        session['cart'] = cart
        session.modified = True
    return redirect(url_for('buyer.cart'))


@bp.route("/orders")
def orders():
    if 'user' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('buyer.login'))

    from ..models import Order, ProductOrder, StockOrder, Product, Stock
    user_orders = Order.query.filter_by(id_user=session['user']['id']).all()

    orders_data = []
    for order in user_orders:
        items = []
        total = 0
        # Get ProductOrder items
        product_orders = ProductOrder.query.filter_by(id_order=order.id_order).all()
        for po in product_orders:
            product = Product.query.get(po.id_product)
            qty = po.count
            price = float(product.price_product)
            title = product.title_product
            if po.ral:
                title += f" RAL {po.ral}"
            items.append({
                'title': title,
                'price': price,
                'qty': qty,
                'product_id': product.id_product,
                'type': 'production'
            })
            total += price * qty

        # Get StockOrder items
        stock_orders = StockOrder.query.filter_by(id_order=order.id_order).all()
        for so in stock_orders:
            stock = Stock.query.get(so.id_stock)
            product = Product.query.get(stock.id_product)
            qty = so.count_order
            price = float(product.price_product)
            title = f"{product.nomenclature_product}"
            if stock.ral_stock:
                title += f" RAL {stock.ral_stock}"
            title += f" (п.{stock.id_stock} от {stock.date_stock.strftime('%d.%m.%Y')})"
            items.append({
                'title': title,
                'price': price,
                'qty': qty,
                'product_id': product.id_product,
                'type': 'stock'
            })
            total += price * qty

        orders_data.append({
            'id': f"order_{order.id_order}",
            'created_at': order.created_at_order.isoformat(),
            'status': order.status_order,
            'items': items,
            'total': total
        })

    return render_template("orders.html", orders=orders_data)


@bp.route("/stock")
def stock():
    from sqlalchemy import text

    # Получаем данные напрямую из таблиц stocks и products
    stock_series = db.session.execute(text("""
        SELECT s.id_stock,
               concat(p.nomenclature_product,
                      CASE WHEN s.ral_stock IS NOT NULL THEN concat(' RAL ', s.ral_stock) ELSE '' END) AS nomenclature_ral,
               concat('п.', s.id_stock, ' от ', to_char(s.date_stock, 'DD.MM.YYYY'), ' до ',
                      to_char(s.date_stock + (p.expiration_month_product || ' months')::interval, 'DD.MM.YYYY')) AS series_info,
               s.count_stock AS remaining_quantity
        FROM stocks s
        JOIN products p ON s.id_product = p.id_product
        WHERE s.count_stock > 0
        ORDER BY nomenclature_ral, series_info
    """)).fetchall()

    # Получаем все продукты для сопоставления названий
    products = get_all_products()
    product_names = {p.nomenclature_product: p.title_product for p in products}
    product_ids = {p.nomenclature_product: p.id_product for p in products}

    # Подготавливаем данные для шаблона
    stock_data = []
    for series in stock_series:
        # Извлекаем базовую номенклатуру из nomenclature_ral
        if ' RAL ' in series.nomenclature_ral:
            base_nomenclature = series.nomenclature_ral.split(' RAL ')[0]
        else:
            base_nomenclature = series.nomenclature_ral

        product_name = product_names.get(base_nomenclature, series.nomenclature_ral)
        product_id = product_ids.get(base_nomenclature)
        if product_id is not None:
            try:
                product_id = int(product_id)
                stock_data.append({
                    'product_name': product_name,
                    'nomenclature_ral': series.nomenclature_ral,
                    'series_info': series.series_info,
                    'remaining_quantity': series.remaining_quantity,
                    'product_id': product_id,
                    'id_stock': series.id_stock
                })
            except (ValueError, TypeError):
                continue  # Skip invalid product IDs

    return render_template("stock.html", stock_data=stock_data)


@bp.route("/stock_detail/<int:id_stock>/")
def stock_detail(id_stock):
    # Получить информацию о остатке по id_stock напрямую из таблиц stocks и products
    from sqlalchemy import text
    stock_series = db.session.execute(text("""
        SELECT s.id_stock,
               concat(p.nomenclature_product,
                      CASE WHEN s.ral_stock IS NOT NULL THEN concat(' RAL ', s.ral_stock) ELSE '' END) AS nomenclature_ral,
               concat('п.', s.id_stock, ' от ', to_char(s.date_stock, 'DD.MM.YYYY'), ' до ',
                      to_char(s.date_stock + (p.expiration_month_product || ' months')::interval, 'DD.MM.YYYY')) AS series_info,
               s.count_stock AS remaining_quantity,
               p.id_product, p.title_product, p.description_product, p.price_product, p.img_path_product
        FROM stocks s
        JOIN products p ON s.id_product = p.id_product
        WHERE s.id_stock = :id_stock
        LIMIT 1
    """), {'id_stock': id_stock}).fetchone()

    if not stock_series:
        flash('Информация о остатке не найдена.')
        return redirect(url_for('buyer.stock'))

    # Создать объект продукта из данных
    from ..models import Product
    product = Product(
        id_product=stock_series.id_product,
        title_product=stock_series.title_product,
        description_product=stock_series.description_product,
        price_product=stock_series.price_product,
        img_path_product=stock_series.img_path_product,
        nomenclature_product=stock_series.nomenclature_ral.split(' RAL ')[0] if ' RAL ' in stock_series.nomenclature_ral else stock_series.nomenclature_ral,
        category_product='',  # Не используется в шаблоне
        expiration_month_product=0,  # Не используется в шаблоне
        created_at_product=None  # Не используется в шаблоне
    )

    stock_info = {
        'nomenclature_ral': stock_series.nomenclature_ral,
        'series_info': stock_series.series_info,
        'remaining_quantity': stock_series.remaining_quantity,
        'id_stock': stock_series.id_stock
    }

    # Вернуть шаблон stock_detail.html
    return render_template("stock_detail.html", product=product, stock_info=stock_info)
