from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..utils import PRODUCTS, STOCKS, ORDERS, USERS, read_json, write_json, gen_id, get_user_by_username, list_json
from pathlib import Path
from datetime import datetime
from ..utils import get_all_chats, get_chat, add_message_to_chat, toggle_bot_for_chat, assign_manager_to_chat, create_chat
from ..chatbot import chatbot

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
@bp.route("/create_user", methods=["GET", "POST"])
def create_user():
    """Создание пользователя (объединенный GET и POST)"""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form.get("role", "buyer")

        # Проверка существования пользователя
        if get_user_by_username(username):
            flash("Пользователь с таким логином уже существует", "error")
            return redirect(url_for("admin.users_management"))

        # Создание пользователя
        user = {
            "id": gen_id("u_"),
            "username": username,
            "password": password,
            "role": role,
            "created_at": datetime.utcnow().isoformat()
        }

        write_json(Path(USERS) / f"{user['id']}.json", user)
        flash(f"Пользователь {username} успешно создан", "success")
        return redirect(url_for("admin.users_management"))

    # GET запрос - перенаправляем на страницу управления пользователями
    return redirect(url_for("admin.users_management"))


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
                print(f"=== DEBUG: Загружен пользователь: {user_data}")
                if user_data:  # Проверяем, что файл не пустой
                    users.append(user_data)
            except Exception as e:
                print(f"=== DEBUG: Ошибка чтения файла {user_file}: {e}")

    print(f"=== DEBUG: Всего пользователей: {len(users)}")
    return render_template("admin_create_user.html", users=users)


@bp.route("/update_user", methods=["POST"])
def update_user():
    """Обновление пользователя"""
    try:
        user_id = request.form["user_id"]
        username = request.form["username"]
        role = request.form["role"]
        password = request.form.get("password", "")

        # Загрузка пользователя
        user_file = Path(USERS) / f"{user_id}.json"
        if not user_file.exists():
            return jsonify({"success": False, "error": "Пользователь не найден"})

        user = read_json(user_file)

        # Проверка уникальности логина (если изменился)
        if user["username"] != username:
            existing_user = get_user_by_username(username)
            if existing_user and existing_user["id"] != user_id:
                return jsonify({"success": False, "error": "Пользователь с таким логином уже существует"})

        # Обновление данных
        user["username"] = username
        user["role"] = role
        if password:  # Обновляем пароль только если указан новый
            user["password"] = password
        user["updated_at"] = datetime.utcnow().isoformat()

        write_json(user_file, user)
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


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
    return render_template('chats.html', chats=chats)


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
        chat = create_chat(user_id, user_name)

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