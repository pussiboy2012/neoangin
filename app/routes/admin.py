import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..utils import PRODUCTS, STOCKS, ORDERS, USERS, read_json, write_json, gen_id, get_user_by_username, list_json
from pathlib import Path
from datetime import datetime
from ..utils import get_all_chats, get_chat, add_message_to_chat, toggle_bot_for_chat, assign_manager_to_chat, create_chat, mark_all_messages_as_read
from ..chatbot import chatbot
import hashlib

bp = Blueprint("admin", __name__, template_folder="../templates")


@bp.before_request
def check_admin():
    if "user" not in session or session["user"].get("role") != "admin":
        return redirect(url_for("buyer.login"))


@bp.route("/")
def admin_index():
    return render_template("admin_dashboard.html")


@bp.route("/create_product", methods=["GET", "POST"])
def create_product():
    if request.method == "POST":
        title = request.form["title"]
        price = float(request.form.get("price", 0))
        pid = gen_id("p_")
        product = {"id": pid, "title": title, "price": price, "created_at": datetime.utcnow().isoformat()}
        write_json(Path(PRODUCTS) / f"{pid}.json", product)
        # init stock
        stock = {"product_id": pid, "qty": int(request.form.get("qty", 0))}
        write_json(Path(STOCKS) / f"{pid}.json", stock)
        flash("Товар создан")
        return redirect(url_for("admin.create_product"))
    return render_template("admin_create_product.html")


# ОБЪЕДИНЕННЫЙ МАРШРУТ - УДАЛИТЬ ДУБЛИКАТЫ
@bp.route("/create_user", methods=["POST"])
def create_user():
    try:
        # Получаем данные из формы
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "").strip()

        print(f"=== DEBUG: Получены данные - username: {username}, email: {email}, role: {role}")

        # Проверяем обязательные поля
        if not all([username, email, full_name, phone, role, password]):
            return jsonify({"success": False, "error": "Все обязательные поля должны быть заполнены"})

        # Для покупателей получаем ИНН и название компании
        inn = request.form.get("inn", "").strip()
        company_name = request.form.get("company_name", "").strip()

        # Для сотрудников устанавливаем фиксированные значения
        if role in ['manager', 'admin']:
            inn = ""
            company_name = "ООО \"Прайм-Топ\""

        # Проверка существующего пользователя
        if get_user_by_username(username):
            return jsonify({"success": False, "error": "Пользователь с таким логином уже существует"})

        if get_user_by_username(email):
            return jsonify({"success": False, "error": "Пользователь с таким email уже существует"})

        # Создание пользователя с правильной структурой
        user = {
            "id": gen_id("u_"),
            "username": username,
            "email": email,
            "full_name": full_name,
            "inn": inn,
            "company_name": company_name,
            "phone": phone,
            "password": hash_password(password),
            "role": role,
            "created_at": datetime.utcnow().isoformat(),
            "company_verified": True
        }

        write_json(Path(USERS) / f"{user['id']}.json", user)
        return jsonify({"success": True})

    except Exception as e:
        print(f"=== DEBUG: Ошибка при создании пользователя: {str(e)}")
        return jsonify({"success": False, "error": f"Внутренняя ошибка сервера: {str(e)}"})

@bp.route("/update_user", methods=["POST"])
def update_user():
    try:
        user_id = request.form["user_id"]
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        full_name = request.form["full_name"].strip()
        inn = request.form["inn"].strip()
        phone = request.form["phone"].strip()
        company_name = request.form["company_name"].strip()
        role = request.form["role"]
        password = request.form.get("password", "")

        # Загружаем существующего пользователя
        user_path = Path(USERS) / f"{user_id}.json"
        if not user_path.exists():
            return jsonify({"success": False, "error": "Пользователь не найден"})

        user = read_json(user_path)

        # Обновляем данные
        user.update({
            "username": username,
            "email": email,
            "full_name": full_name,
            "inn": inn,
            "company_name": company_name,
            "phone": phone,
            "role": role
        })

        # Обновляем пароль если указан новый
        if password:
            user["password"] = hash_password(password)

        write_json(user_path, user)
        return jsonify({"success": True})

    except Exception as e:
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
    products = list_json(PRODUCTS)

    # Подготавливаем данные для шаблона
    stocks_data = {}
    total_stock = 0
    in_stock_count = 0
    out_of_stock_count = 0

    for product in products:
        product_id = product["id"]
        stock_file = Path(STOCKS) / f"{product_id}.json"

        if stock_file.exists():
            stock_data = read_json(stock_file)
            stock_qty = stock_data.get("qty", 0) if stock_data else 0
        else:
            stock_qty = 0

        # Сохраняем остатки
        stocks_data[product_id] = {"qty": stock_qty}

        # Добавляем stock_qty к продукту для статистики
        product["stock_qty"] = stock_qty

        # Считаем статистику
        total_stock += stock_qty
        if stock_qty > 0:
            in_stock_count += 1
        else:
            out_of_stock_count += 1

    if request.method == "POST":
        pid = request.form["product_id"]
        qty = int(request.form.get("qty", 0))
        write_json(Path(STOCKS) / f"{pid}.json", {"product_id": pid, "qty": qty})
        flash("Остаток обновлён")
        return redirect(url_for("admin.stocks"))


    return render_template("admin_stocks.html",
                           products=products,
                           stocks=stocks_data,
                           total_stock=total_stock,
                           in_stock_count=in_stock_count,
                           out_of_stock_count=out_of_stock_count)

@bp.route("/orders")
def admin_orders():
    orders = list_json(ORDERS)
    return render_template("admin_orders.html", orders=orders)


@bp.route("/order/approve/<order_id>")
def approve_order(order_id):
    path = Path(ORDERS) / f"{order_id}.json"
    order = read_json(path)
    if not order:
        flash("Заказ не найден")
        return redirect(url_for("admin.admin_orders"))
    order["status"] = "approved"
    write_json(path, order)
    flash("Заказ одобрен")
    return redirect(url_for("admin.admin_orders"))


@bp.route("/users")
def users_management():
    """Страница управления пользователями"""
    users = []
    users_path = Path(USERS)

    print(f"=== DEBUG: Путь к пользователям: {users_path}")
    print(f"=== DEBUG: Существует ли папка: {users_path.exists()}")

    if users_path.exists():
        for user_file in users_path.glob("*.json"):
            try:
                user_data = read_json(user_file)
                if user_data:  # Проверяем, что файл не пустой
                    users.append(user_data)
            except Exception as e:
                print(f"=== DEBUG: Ошибка чтения файла {user_file}: {e}")

    return render_template("admin_create_user.html", users=users)

@bp.route("/delete_user", methods=["POST"])
def delete_user():
    """Удаление пользователя"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "ID пользователя не указан"})

        user_file = Path(USERS) / f"{user_id}.json"

        # Нельзя удалить самого себя
        if session.get("user") and session["user"]["id"] == user_id:
            return jsonify({"success": False, "error": "Нельзя удалить свой собственный аккаунт"})

        if user_file.exists():
            user_file.unlink()  # Удаляем файл пользователя
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Пользователь не найден"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/get_user/<user_id>")
def get_user(user_id):
    """Получение данных пользователя для редактирования"""
    try:
        user_file = Path(USERS) / f"{user_id}.json"
        if user_file.exists():
            user = read_json(user_file)
            # Не возвращаем пароль
            user_data = {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "created_at": user.get("created_at", "")
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