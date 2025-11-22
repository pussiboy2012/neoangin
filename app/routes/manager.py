from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from ..db_helpers import get_all_users, get_all_products, get_orders_by_user, get_all_orders, update_order_status
from ..models import db, Product, Stock
from sqlalchemy import text
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from ..utils import USERS, read_json
from pathlib import Path
from ..utils import get_all_chats, get_chat, add_message_to_chat, toggle_bot_for_chat, assign_manager_to_chat, create_chat, mark_all_messages_as_read

bp = Blueprint("manager", __name__, template_folder="../templates")


@bp.before_request
def check_manager():
    if "user" not in session or session["user"].get("role") not in ["manager", "admin"]:
        flash("Требуется вход менеджера")
        return redirect(url_for("buyer.login"))


@bp.route("/")
def manager_index():
    return render_template("manager_dashboard.html")


@bp.route("/orders")
def orders():
    """Страница управления заказами для менеджера с фильтрацией"""
    # Получаем параметры фильтрации
    sort_by = request.args.get('sort_by', 'date')
    filter_status = request.args.get('filter_status', '')

    # Получаем все заказы
    orders = get_all_orders()

    # Применяем фильтрацию по статусу
    if filter_status:
        orders = [o for o in orders if o.status_order == filter_status]

    # Сортируем заказы
    if sort_by == 'date':
        orders.sort(key=lambda x: x.created_at_order or datetime.min, reverse=True)
    elif sort_by == 'status':
        orders.sort(key=lambda x: x.status_order)
    elif sort_by == 'total':
        # Здесь нужно будет добавить расчет общей суммы заказа
        pass

    # Подготавливаем данные для шаблона (аналогично предыдущей версии)
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

        # Получаем товары из ProductOrder
        try:
            if hasattr(order, 'order_items'):
                product_items = list(order.order_items)  # Преобразуем в список

                for item in product_items:
                    product = getattr(item, 'product', None)
                    title = getattr(product, 'title_product', 'Товар не найден') if product else 'Товар не найден'
                    ral = getattr(item, 'ral', None)

                    if ral:
                        title += f" RAL {ral}"

                    item_dict = {
                        'product_id': getattr(item, 'id_product', 0),
                        'title': title,
                        'qty': getattr(item, 'count', 0),
                        'price': float(getattr(product, 'price_product', 0)) if product else 0,
                        'ral': ral
                    }
                    order_dict['items'].append(item_dict)
                    order_dict['total'] += item_dict['qty'] * item_dict['price']
            else:
                print("  No order_items attribute")
        except Exception as e:
            print(f"  Error processing product items: {e}")

        # Получаем товары из StockOrder
        try:
            if hasattr(order, 'stock_order_items'):
                stock_items = list(order.stock_order_items)  # Преобразуем в список

                for item in stock_items:
                    stock = getattr(item, 'stock', None)
                    if stock:
                        product = getattr(stock, 'product', None)
                        title = getattr(product, 'nomenclature_product', 'Товар') if product else 'Товар'
                        ral = getattr(stock, 'ral_stock', None)
                        date_stock = getattr(stock, 'date_stock', None)

                        if ral:
                            title += f" RAL {ral}"
                        if date_stock:
                            title += f" (п.{getattr(stock, 'id_stock', '')} от {date_stock.strftime('%d.%m.%Y')})"

                        item_dict = {
                            'product_id': getattr(stock, 'id_product', 0),
                            'title': title,
                            'qty': getattr(item, 'count_order', 0) or 0,
                            'price': float(getattr(product, 'price_product', 0)) if product else 0,
                            'ral': ral
                        }
                        order_dict['items'].append(item_dict)
                        order_dict['total'] += item_dict['qty'] * item_dict['price']
            else:
                print("  No stock_order_items attribute")
        except Exception as e:
            print(f"  Error processing stock items: {e}")


        orders_data.append(order_dict)
    return render_template("manager_orders.html",
                           orders=orders_data,
                           sort_by=sort_by,
                           filter_status=filter_status)

@bp.route("/order/approve/<order_id>")
def approve_order(order_id):
    """Одобрение заказа"""
    order = update_order_status(order_id, "approved")
    if not order:
        flash("Заказ не найден")
        return redirect(url_for("manager.orders"))
    flash("Заказ одобрен")
    return redirect(url_for("manager.orders"))


@bp.route("/order/reject/<order_id>")
def reject_order(order_id):
    """Отклонение заказа"""
    order = update_order_status(order_id, "rejected")
    if not order:
        flash("Заказ не найден")
        return redirect(url_for("manager.orders"))
    flash("Заказ отклонен")
    return redirect(url_for("manager.orders"))


@bp.route("/stocks")
def stocks():
    """Страница управления остатками для менеджера"""
    # Получаем данные из представления product_stock_series
    stock_series = db.session.execute(text("""
        SELECT nomenclature_ral, series_info, remaining_quantity
        FROM product_stock_series
        ORDER BY nomenclature_ral, series_info
    """)).fetchall()

    # Получаем все продукты
    products = get_all_products()

    # Подготавливаем данные для шаблона
    total_stock = 0
    in_stock_count = 0
    out_of_stock_count = 0

    for product in products:
        stock = Stock.query.filter_by(id_product=product.id_product).first()
        stock_qty = stock.count_stock if stock else 0

        # Добавляем данные к продукту для статистики
        product.stock_qty = stock_qty

        # Считаем статистику
        total_stock += stock_qty
        if stock_qty > 0:
            in_stock_count += 1
        else:
            out_of_stock_count += 1

    return render_template("manager_stocks.html",
                           products=products,
                           stock_series=stock_series,
                           total_stock=total_stock,
                           in_stock_count=in_stock_count,
                           out_of_stock_count=out_of_stock_count)


@bp.route("/products")
def products():
    """Страница редактирования товаров для менеджера"""
    products = get_all_products()
    return render_template("manager_products.html", products=products)


@bp.route("/product/edit/<product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    """Редактирование товара"""
    product = Product.query.get(product_id)
    if not product:
        flash("Товар не найден")
        return redirect(url_for("manager.products"))

    if request.method == "POST":
        try:
            product.title_product = request.form["title"]
            product.price_product = float(request.form.get("price", 0))
            product.category_product = request.form["category"]
            product.description_product = request.form["description"]
            product.expiration_month_product = int(request.form["expiration_month"])
            product.nomenclature_product = request.form["nomenclature"]

            # Handle image upload
            img_file = request.files.get("img_file")
            if img_file and img_file.filename:
                # Create uploads directory if it doesn't exist
                uploads_dir = os.path.join(bp.root_path, '../..', 'static', 'uploads')
                os.makedirs(uploads_dir, exist_ok=True)

                # Secure filename and save
                filename = secure_filename(img_file.filename)
                img_file.save(os.path.join(uploads_dir, filename))
                product.img_product = f"uploads/{filename}"

            db.session.commit()
            flash("Товар успешно обновлен")
            return redirect(url_for("manager.products"))

        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при обновлении товара: {str(e)}")

    return render_template("manager_edit_product.html", product=product)


# Переименовал для единообразия
@bp.route('/chats')
def chats():
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

    return render_template('manager_chats.html', chats=processed_chats)  # <- исправлено на manager_chats.html


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
def chat_detail(user_id):
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

    # ИСПРАВЛЕНИЕ: передаем chat (один чат) в шаблон деталей
    return render_template('manager_chat_detail.html', chat=chat)  # <- передаем chat, а не chats


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
    if session.get('user', {}).get('role') not in ['admin', 'manager']:
        return jsonify({'error': 'Доступ запрещен'}), 403

    manager_id = request.json.get('manager_id')
    success = assign_manager_to_chat(user_id, manager_id)

    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Чат не найден'}), 404


@bp.route("/reports")
def reports():
    """Страница отчетов для менеджера"""
    # Базовая статистика для демонстрации
    total_products = Product.query.count()
    total_orders = len(get_all_orders())
    pending_orders = len([o for o in get_all_orders() if o.status_order == 'pending'])

    return render_template("manager_reports.html",
                           total_products=total_products,
                           total_orders=total_orders,
                           pending_orders=pending_orders)


@bp.route("/select_customer", methods=["GET", "POST"])
def select_customer():
    customers = [u for u in get_all_users() if u.role_user == "buyer"]
    selected = None
    orders = []
    if request.method == "POST":
        selected = request.form.get("customer_id")
        orders = get_orders_by_user(int(selected))
    return render_template("manager_select.html", customers=customers, selected=selected, orders=orders)


@bp.route("/catalog")
def manager_catalog():
    products = get_all_products()
    return render_template("catalog.html", products=products)