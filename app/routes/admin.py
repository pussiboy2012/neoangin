import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from ..utils import PRODUCTS, STOCKS, ORDERS, USERS, read_json, write_json, gen_id, get_user_by_username, list_json
from pathlib import Path
from datetime import datetime
from ..utils import get_all_chats, get_chat, add_message_to_chat, toggle_bot_for_chat, assign_manager_to_chat, create_chat, mark_all_messages_as_read
from ..chatbot import chatbot
import hashlib
from ..models import db, Product, Stock, User, Analyzis, Order
from ..db_helpers import create_product, update_stock, create_user
from sqlalchemy import text

bp = Blueprint("admin", __name__, template_folder="../templates")


@bp.before_request
def check_admin():
    if "user" not in session or session["user"].get("role") != "admin":
        return redirect(url_for("buyer.login"))


@bp.route("/")
def admin_index():
    # Query real stats from database
    new_orders = Order.query.count()
    products_count = db.session.query(Stock.id_product).distinct().count()
    active_users = User.query.filter(User.role_user == 'buyer').count()
    low_stock = Stock.query.filter(Stock.count_stock < 10).count()

    return render_template("admin_dashboard.html",
                           new_orders=new_orders,
                           products_count=products_count,
                           active_users=active_users,
                           low_stock=low_stock)


@bp.route("/create_product", methods=["GET", "POST"])
def create_product_page():
    if request.method == "POST":
        title = request.form["title"]
        price = float(request.form.get("price", 0))
        category = request.form["category"]
        description = request.form["description"]
        expiration_month = int(request.form["expiration_month"])
        nomenclature = request.form["nomenclature"]
        # Handle image upload
        img_file = request.files.get("img_file")
        img_path = None
        if img_file and img_file.filename:
            # Create uploads directory if it doesn't exist
            uploads_dir = os.path.join(bp.root_path, '../..', 'static', 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)

            # Secure filename and save
            filename = secure_filename(img_file.filename)
            img_file.save(os.path.join(uploads_dir, filename))
            img_path = f"uploads/{filename}"

        # Create product in DB
        product = create_product(title, price, category, description, img_path, expiration_month, nomenclature)

        flash("Товар создан")
        return redirect(url_for("admin.create_product_page"))
    return render_template("admin_create_product.html")


@bp.route("/create_user", methods=["POST"])
def create_user_route():
    try:
        # Получаем данные из формы
        email = request.form.get("email", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "").strip()

        print(f"=== DEBUG: Получены данные - email: {email}, role: {role}")

        # Проверяем обязательные поля
        if not all([email, full_name, phone, role, password]):
            return jsonify({"success": False, "error": "Все обязательные поля должны быть заполнены"})

        # Для покупателей получаем ИНН и название компании
        inn = request.form.get("inn", "").strip()
        company_name = request.form.get("company_name", "").strip()

        # Для сотрудников устанавливаем фиксированные значения
        if role in ['manager', 'admin']:
            inn = ""
            company_name = "ООО \"Прайм-Топ\""

        # Проверяем обязательные поля для покупателей
        if role == 'buyer' and not company_name:
            return jsonify({"success": False, "error": "Название компании обязательно для покупателей. Пожалуйста, проверьте ИНН."})

        # Проверка существующего пользователя
        from ..db_helpers import get_user_by_email
        if get_user_by_email(email):
            return jsonify({"success": False, "error": "Пользователь с таким email уже существует"})

        # Создание пользователя через DB
        create_user(email, full_name, inn, company_name, phone, password, role)
        return jsonify({"success": True})

    except Exception as e:
        print(f"=== DEBUG: Ошибка при создании пользователя: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "error": f"Внутренняя ошибка сервера: {str(e)}"})

@bp.route("/update_user", methods=["POST"])
def update_user():
    try:
        user_id = request.form["user_id"]
        email = request.form["email"].strip().lower()
        full_name = request.form["full_name"].strip()
        inn = request.form["inn"].strip()
        phone = request.form["phone"].strip()
        company_name = request.form["company_name"].strip()
        role = request.form["role"]
        password = request.form.get("password", "")

        # Загружаем существующего пользователя
        user = User.query.filter_by(id_user=user_id).first()
        if not user:
            return jsonify({"success": False, "error": "Пользователь не найден"})

        # Обновляем данные
        user.email_user = email
        user.fullname_user = full_name
        user.inn_user = inn
        user.company_name_user = company_name
        user.phone_user = phone
        user.role_user = role

        # Обновляем пароль если указан новый
        if password:
            hashed, salt = hash_password(password)
            user.password_hash_user = hashed + ':' + salt

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})

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
DADATA_TOKEN = os.environ.get("DADATA_TOKEN")


@bp.route("/verify_inn", methods=["POST"])
def verify_inn():
    """Проверка ИНН через DaData API"""
    inn = request.json.get('inn', '').strip()

    print(f"=== DEBUG: Проверка ИНН: {inn}")
    print(f"=== DEBUG: DADATA_TOKEN: {DADATA_TOKEN}")

    if not inn or not inn.isdigit() or len(inn) not in [10, 12]:
        return jsonify({'success': False, 'error': 'Неверный формат ИНН'})

    if not DADATA_TOKEN:
        return jsonify({'success': False, 'error': 'Сервис проверки ИНН недоступен'})

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
                print(f"=== DEBUG: Найдена компания: {company.get('value')}")
                return jsonify({
                    'success': True,
                    'company_name': company.get('value', ''),
                    'full_name': company.get('data', {}).get('name', {}).get('full', ''),
                    'inn': company.get('data', {}).get('inn', ''),
                    'kpp': company.get('data', {}).get('kpp', ''),
                    'address': company.get('data', {}).get('address', {}).get('value', '')
                })
            else:
                print("=== DEBUG: Компания не найдена в ответе")
                return jsonify({'success': False, 'error': 'Компания с таким ИНН не найдена'})
        elif response.status_code == 403:
            print("=== DEBUG: Ошибка 403 - неверный токен")
            return jsonify({'success': False, 'error': 'Неверный токен доступа к сервису'})
        elif response.status_code == 429:
            print("=== DEBUG: Ошибка 429 - превышен лимит запросов")
            return jsonify({'success': False, 'error': 'Превышен лимит запросов к сервису'})
        else:
            print(f"=== DEBUG: Ошибка сервиса: {response.status_code}")
            return jsonify({'success': False, 'error': f'Ошибка сервиса проверки ИНН: {response.status_code}'})

    except requests.exceptions.RequestException as e:
        print(f"=== DEBUG: Ошибка подключения: {e}")
        return jsonify({'success': False, 'error': 'Ошибка подключения к сервису'})
    except Exception as e:
        print(f"=== DEBUG: Внутренняя ошибка: {e}")
        return jsonify({'success': False, 'error': 'Внутренняя ошибка сервера'})

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()



@bp.route("/stocks", methods=["GET", "POST"])
def stocks():
    # Получаем данные о сериях товаров напрямую из таблиц stocks и products
    stock_series = db.session.execute(text("""
        SELECT
            CONCAT(p.nomenclature_product,
                CASE
                    WHEN s.ral_stock IS NOT NULL THEN CONCAT(' RAL ', s.ral_stock)
                    ELSE ''
                END) AS nomenclature_ral,
            CONCAT('п.', s.id_stock, ' от ', TO_CHAR(s.date_stock, 'DD.MM.YYYY'), ' до ',
                TO_CHAR(s.date_stock + INTERVAL '1 month' * p.expiration_month_product, 'DD.MM.YYYY')) AS series_info,
            s.count_stock AS remaining_quantity
        FROM stocks s
        JOIN products p ON s.id_product = p.id_product
        WHERE s.count_stock > 0
        ORDER BY p.title_product, s.ral_stock, s.date_stock
    """)).fetchall()

    # Получаем все продукты для формы обновления
    products = Product.query.all()

    # Подготавливаем данные для шаблона
    stocks_data = {}
    total_stock = 0
    in_stock_count = 0
    out_of_stock_count = 0

    for product in products:
        stock = Stock.query.filter_by(id_product=product.id_product).first()
        stock_qty = stock.count_stock if stock else 0
        ral = stock.ral_stock if stock else None
        date = stock.date_stock if stock else None
        analyzis = None
        if stock and stock.id_analyzis:
            analyzis = Analyzis.query.get(stock.id_analyzis)

        # Сохраняем остатки с дополнительными данными
        stocks_data[product.id_product] = {
            "qty": stock_qty,
            "ral": ral,
            "date": date,
            "analyzis": analyzis
        }

        # Добавляем данные к продукту для статистики
        product.stock_qty = stock_qty
        product.stock_ral = ral
        product.analyzis = analyzis

        # Считаем статистику
        total_stock += stock_qty
        if stock_qty > 0:
            in_stock_count += 1
        else:
            out_of_stock_count += 1

    # Получаем данные о заказах и их составе
    orders = Order.query.all()
    orders_data = []
    for order in orders:
        order_dict = {
            'id': order.id_order,
            'user_id': order.id_user,
            'status': order.status_order,
            'created_at': order.created_at_order.isoformat() if order.created_at_order else '',
            'total': 0,
            'items': []
        }
        # Handle ProductOrder items
        for item in order.order_items:
            product = item.product
            title = product.title_product
            if item.ral:
                title += f" RAL {item.ral}"
            item_dict = {
                'product_id': item.id_product,
                'title': title,
                'qty': item.count,
                'price': float(product.price_product) if product else 0,
                'ral': item.ral
            }
            order_dict['items'].append(item_dict)
            order_dict['total'] += item_dict['qty'] * item_dict['price']

        # Handle StockOrder items
        for item in order.stock_order_items:
            stock = item.stock
            if stock:
                product = stock.product
                title = f"{product.nomenclature_product}"
                if stock.ral_stock:
                    title += f" RAL {stock.ral_stock}"
                title += f" (п.{stock.id_stock} от {stock.date_stock.strftime('%d.%m.%Y')})"
                item_dict = {
                    'product_id': stock.id_product,
                    'title': title,
                    'qty': item.count_order or 0,
                    'price': float(product.price_product) if product else 0,
                    'ral': stock.ral_stock
                }
                order_dict['items'].append(item_dict)
                order_dict['total'] += item_dict['qty'] * item_dict['price']

        orders_data.append(order_dict)

    if request.method == "POST":
        nomenclature = request.form.get("nomenclature", "").strip()
        qty = int(request.form.get("qty", 0))
        ral = request.form.get("ral", "").strip() or None
        date_str = request.form.get("date", "").strip()

        if not date_str:
            flash("Дата производства партии обязательна")
            return redirect(url_for("admin.stocks"))

        try:
            date_stock = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Неверный формат даты")
            return redirect(url_for("admin.stocks"))

        # Найти продукт по номенклатуре
        product = Product.query.filter_by(nomenclature_product=nomenclature).first()
        if not product:
            flash("Товар с такой номенклатурой не найден")
            return redirect(url_for("admin.stocks"))

        pid = product.id_product

        # Проверить, существует ли уже запись с таким же продуктом, RAL и датой
        existing_stock = Stock.query.filter_by(
            id_product=pid,
            ral_stock=ral,
            date_stock=date_stock
        ).first()

        if existing_stock:
            # Если запись существует, суммируем количества
            existing_stock.count_stock += qty
        else:
            # Создаем новую запись
            new_stock = Stock(
                id_product=pid,
                count_stock=qty,
                ral_stock=ral,
                date_stock=date_stock
            )
            db.session.add(new_stock)

        db.session.commit()
        flash("Остаток обновлён")
        return redirect(url_for("admin.stocks"))

    return render_template("admin_stocks.html",
                           products=products,
                           stocks=stocks_data,
                           stock_series=stock_series,
                           total_stock=total_stock,
                           in_stock_count=in_stock_count,
                           out_of_stock_count=out_of_stock_count,
                           orders=orders_data)

@bp.route("/orders")
def admin_orders():
    from ..db_helpers import get_all_orders, get_user_by_id
    from ..utils import get_chat

    orders = get_all_orders()

    # Get sorting and filtering parameters
    sort_by = request.args.get('sort_by', 'date')
    filter_customer = request.args.get('filter_customer', '').strip()

    # Prepare orders data for template
    orders_data = []
    for order in orders:
        user = get_user_by_id(order.id_user)
        company_name = user.company_name_user if user else 'N/A'
        customer_name = user.fullname_user if user else 'N/A'

        # Get assigned manager from chat
        chat = get_chat(str(order.id_user))
        manager_name = 'Не назначен'
        if chat and chat.get('assigned_manager'):
            manager_user = get_user_by_id(chat['assigned_manager'])
            if manager_user:
                manager_name = manager_user.fullname_user

        order_dict = {
            'id': order.id_order,
            'user_id': order.id_user,
            'company_name': company_name,
            'customer_name': customer_name,
            'manager_name': manager_name,
            'status': order.status_order,
            'created_at': order.created_at_order.isoformat() if order.created_at_order else '',
            'total': 0,
            'items': []
        }
        # Calculate total and get items from both ProductOrder and StockOrder
        # Handle ProductOrder items
        for item in order.order_items:
            product = item.product
            title = product.title_product
            if item.ral:
                title += f" RAL {item.ral}"
            item_dict = {
                'product_id': item.id_product,
                'title': title,
                'qty': item.count,
                'price': float(product.price_product) if product else 0,
                'ral': item.ral
            }
            order_dict['items'].append(item_dict)
            order_dict['total'] += item_dict['qty'] * item_dict['price']

        # Handle StockOrder items
        for item in order.stock_order_items:
            stock = item.stock
            if stock:
                product = stock.product
                title = f"{product.nomenclature_product}"
                if stock.ral_stock:
                    title += f" RAL {stock.ral_stock}"
                title += f" (п.{stock.id_stock} от {stock.date_stock.strftime('%d.%m.%Y')})"
                item_dict = {
                    'product_id': stock.id_product,
                    'title': title,
                    'qty': item.count_order or 0,
                    'price': float(product.price_product) if product else 0,
                    'ral': stock.ral_stock
                }
                order_dict['items'].append(item_dict)
                order_dict['total'] += item_dict['qty'] * item_dict['price']

        orders_data.append(order_dict)

    # Apply filtering
    if filter_customer:
        orders_data = [o for o in orders_data if filter_customer.lower() in o['company_name'].lower()]

    # Apply sorting
    if sort_by == 'date':
        orders_data.sort(key=lambda x: x['created_at'], reverse=True)
    elif sort_by == 'customer':
        orders_data.sort(key=lambda x: x['company_name'].lower())
    elif sort_by == 'status':
        status_order = {'pending_moderation': 0, 'approved': 1, 'completed': 2, 'cancelled': 3}
        orders_data.sort(key=lambda x: status_order.get(x['status'], 4))

    return render_template("admin_orders.html", orders=orders_data, sort_by=sort_by, filter_customer=filter_customer)


@bp.route("/order/approve/<order_id>")
def approve_order(order_id):
    from ..db_helpers import update_order_status
    order = update_order_status(order_id, "approved")
    if not order:
        flash("Заказ не найден")
        return redirect(url_for("admin.admin_orders"))
    flash("Заказ одобрен")
    return redirect(url_for("admin.admin_orders"))


@bp.route("/order/update_status/<order_id>", methods=["POST"])
def update_order_status_route(order_id):
    """Обновление статуса заказа"""
    try:
        new_status = request.form.get("status")
        if not new_status:
            return jsonify({"success": False, "error": "Статус не указан"})

        valid_statuses = ["pending_moderation", "approved", "completed", "cancelled"]
        if new_status not in valid_statuses:
            return jsonify({"success": False, "error": "Неверный статус"})

        from ..db_helpers import update_order_status
        order = update_order_status(order_id, new_status)
        if not order:
            return jsonify({"success": False, "error": "Заказ не найден"})

        status_names = {
            "pending_moderation": "На модерации",
            "approved": "Одобрен",
            "completed": "Выполнен",
            "cancelled": "Отменен"
        }

        return jsonify({
            "success": True,
            "message": f"Статус заказа изменен на '{status_names.get(new_status, new_status)}'"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/order/cancel/<order_id>", methods=["POST"])
def cancel_order(order_id):
    """Отмена заказа"""
    try:
        from ..db_helpers import update_order_status
        order = update_order_status(order_id, "cancelled")
        if not order:
            return jsonify({"success": False, "error": "Заказ не найден"})

        return jsonify({
            "success": True,
            "message": "Заказ отменен"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/users")
def users_management():
    """Страница управления пользователями"""
    users = User.query.all()
    # Преобразуем в формат, ожидаемый шаблоном
    users_data = []
    for user in users:
        users_data.append({
            "id": user.id_user,
            "username": user.email_user,
            "email": user.email_user,
            "full_name": user.fullname_user,
            "inn": user.inn_user,
            "company_name": user.company_name_user,
            "phone": user.phone_user,
            "role": user.role_user,
            "created_at": user.created_at_user.isoformat() if user.created_at_user else "",
            "company_verified": user.company_verified_user
        })

    return render_template("admin_create_user.html", users=users_data)

@bp.route("/delete_user", methods=["POST"])
def delete_user():
    """Удаление пользователя"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "ID пользователя не указан"})

        # Нельзя удалить самого себя
        if session.get("user") and str(session["user"]["id"]) == str(user_id):
            return jsonify({"success": False, "error": "Нельзя удалить свой собственный аккаунт"})

        user = User.query.filter_by(id_user=user_id).first()
        if user:
            db.session.delete(user)
            db.session.commit()
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Пользователь не найден"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


@bp.route("/get_user/<user_id>")
def get_user(user_id):
    """Получение данных пользователя для редактирования"""
    try:
        user = User.query.filter_by(id_user=user_id).first()
        if user:
            # Не возвращаем пароль
            user_data = {
                "id": user.id_user,
                "username": user.username_user,
                "email": user.email_user,
                "full_name": user.fullname_user,
                "inn": user.inn_user,
                "company_name": user.company_name_user,
                "phone": user.phone_user,
                "role": user.role_user,
                "created_at": user.created_at_user.isoformat() if user.created_at_user else ""
            }
            return jsonify({"success": True, "user": user_data})
        else:
            return jsonify({"success": False, "error": "Пользователь не найден"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route('/chats')
def admin_chats():
    """Страница со списком всех чатов"""
    if session.get('user', {}).get('role') not in ['admin', 'manager']:
        return redirect(url_for('buyer.login'))

    chats = get_all_chats()

    # Обрабатываем данные для шаблона
    processed_chats = []
    for chat in chats:
        # Получаем информацию о пользователе
        user_file = Path(USERS) / f"{chat['user_id']}.json"
        user_name = chat.get('user_name', 'Покупатель')
        if user_file.exists():
            user_data = read_json(user_file)
            user_name = user_data.get('username', user_data.get('full_name', user_name))

        # Форматируем время последнего сообщения
        last_message_time = None
        if chat.get('last_message'):
            last_message_time = format_chat_time(chat['last_message']['timestamp'])

        processed_chats.append({
            'user_id': chat['user_id'],
            'user_name': user_name,
            'bot_enabled': chat.get('bot_enabled', True),
            'manager_id': chat.get('assigned_manager'),
            'last_message': chat.get('last_message'),
            'unread_count': chat.get('unread_count', 0),
            'last_message_time': last_message_time
        })

    # Сортируем по времени последнего сообщения (сначала новые)
    processed_chats.sort(key=lambda x: x['last_message_time'] or '', reverse=True)

    return render_template('chats.html', chats=processed_chats)


def format_chat_time(timestamp):
    """Форматирует время для отображения в списке чатов"""
    if not timestamp:
        return None
    try:
        if 'T' in timestamp:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%H:%M')
        return timestamp
    except:
        return timestamp

@bp.route('/api/chat/<user_id>/mark_read', methods=['POST'])
def mark_chat_read(user_id):
    """Помечает все сообщения в чате как прочитанные"""
    if session.get('user', {}).get('role') not in ['admin', 'manager']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    try:
        success = mark_all_messages_as_read(user_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/chat/<user_id>')
def admin_chat_detail(user_id):
    """Детальная страница чата"""
    if session.get('user', {}).get('role') not in ['admin', 'manager']:
        return redirect(url_for('buyer.login'))

    chat = get_chat(user_id)
    if not chat:
        # Создаем чат если его нет
        user_data = read_json(Path(USERS) / f"{user_id}.json")
        user_name = user_data.get('full_name', 'Покупатель') if user_data else 'Покупатель'
        company_name = user_data.get('company_name', 'ООО ДАБАТА') if user_data else 'ООО ДАБАТА'
        chat = create_chat(user_id, user_name, company_name)

    return render_template('chat_detail.html', chat=chat)


@bp.route('/api/chat/<user_id>/message', methods=['POST'])
def send_manager_message(user_id):
    """Отправка сообщения от менеджера"""
    if session.get('user', {}).get('role') not in ['admin', 'manager']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    message = request.json.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Пустое сообщение'}), 400

    # Сохраняем сообщение менеджера
    add_message_to_chat(user_id, "manager", message)

    return jsonify({'success': True})

@bp.route('/api/chat/<user_id>/messages')
def get_chat_messages(user_id):
    """Получение сообщений чата (для AJAX обновления)"""
    if session.get('user', {}).get('role') not in ['admin', 'manager']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    chat = get_chat(user_id)
    if not chat:
        return jsonify({'messages': []})

    # Возвращаем все сообщения чата
    return jsonify({'messages': chat.get('messages', [])})


@bp.route('/api/chat/<user_id>/toggle_bot', methods=['POST'])
def toggle_chat_bot(user_id):
    """Включение/выключение бота для чата"""
    if session.get('user', {}).get('role') not in ['admin', 'manager']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    enabled = request.json.get('enabled', False)
    success = toggle_bot_for_chat(user_id, enabled)

    if success:
        return jsonify({'success': True, 'bot_enabled': enabled})
    else:
        return jsonify({'error': 'Чат не найден'}), 404


@bp.route('/api/chat/<user_id>/assign', methods=['POST'])
def assign_chat_manager(user_id):
    """Назначение менеджера на чат"""
    if session.get('user', {}).get('role') not in ['admin']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    manager_id = request.json.get('manager_id')
    success = assign_manager_to_chat(user_id, manager_id)

    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Чат не найден'}), 404
    
@bp.route("/analytics")
def analytics():
    """Страница аналитики для администратора"""
    from ..analytics import (
        get_sales_trends, get_product_popularity, get_user_activity_metrics,
        get_stock_levels, get_order_status_distribution, get_revenue_analysis,
        get_analyzis_visualization, get_dashboard_metrics
    )

    # Получаем параметры фильтров из запроса
    filters = {
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'category': request.args.get('category'),
        'user_role': request.args.get('user_role'),
        'product_id': request.args.get('product_id'),
        'ral': request.args.get('ral'),
        'group_by': request.args.get('group_by', 'month'),
        'metric_x': request.args.get('metric_x', 'glitter'),
        'metric_y': request.args.get('metric_y', 'viskosity')
    }

    # Получаем данные для фильтров
    categories = db.session.query(Product.category_product).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]

    products = Product.query.all()

    ral_colors = db.session.query(Stock.ral_stock).distinct().all()
    ral_colors = [ral[0] for ral in ral_colors if ral[0]]

    # Генерируем графики
    sales_trends_chart = get_sales_trends(
        start_date=filters['start_date'],
        end_date=filters['end_date'],
        category=filters['category'],
        user_role=filters['user_role']
    )

    product_popularity_chart = get_product_popularity(
        start_date=filters['start_date'],
        end_date=filters['end_date']
    )

    user_activity_chart = get_user_activity_metrics(
        start_date=filters['start_date'],
        end_date=filters['end_date'],
        role=filters['user_role']
    )

    stock_levels_chart = get_stock_levels(
        product_id=filters['product_id'],
        ral=filters['ral']
    )

    order_status_chart = get_order_status_distribution(
        start_date=filters['start_date'],
        end_date=filters['end_date']
    )

    revenue_analysis_chart = get_revenue_analysis(
        start_date=filters['start_date'],
        end_date=filters['end_date'],
        group_by=filters['group_by']
    )

    analyzis_chart = get_analyzis_visualization(
        product_id=filters['product_id'],
        metric_x=filters['metric_x'],
        metric_y=filters['metric_y']
    )

    # Получаем метрики для дашборда
    metrics = get_dashboard_metrics()

    return render_template("admin_analytics.html",
                         sales_trends_chart=sales_trends_chart,
                         product_popularity_chart=product_popularity_chart,
                         user_activity_chart=user_activity_chart,
                         stock_levels_chart=stock_levels_chart,
                         order_status_chart=order_status_chart,
                         revenue_analysis_chart=revenue_analysis_chart,
                         analyzis_chart=analyzis_chart,
                         metrics=metrics,
                         categories=categories,
                         products=products,
                         ral_colors=ral_colors,
                         current_filters=filters,
                         current_date=datetime.now().strftime('%d.%m.%Y %H:%M'))
