from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..utils import PRODUCTS, USERS, ORDERS, STOCKS, read_json, write_json, list_json, gen_id, login_required, get_user_by_username
from pathlib import Path
from datetime import datetime

bp = Blueprint("buyer", __name__)

@bp.route("/")
def index():
    return render_template("index.html")

# ---- auth ----
@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = "buyer"
        if get_user_by_username(username):
            flash("Пользователь существует")
            return redirect(url_for("buyer.register"))
        user = {"id": gen_id("u_"), "username": username, "password": password, "role": role, "created_at": datetime.utcnow().isoformat()}
        write_json(Path(USERS) / f"{user['id']}.json", user)
        flash("Зарегистрирован")
        return redirect(url_for("buyer.login"))
    return render_template("register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = get_user_by_username(username)
        if not user or user.get("password") != password:
            flash("Неверные учётные данные")
            return redirect(url_for("buyer.login"))
        session["user"] = {"id": user["id"], "username": user["username"], "role": user["role"]}
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
    cart = session.get("cart", {})

    if not cart:
        flash("Корзина пуста")
        return redirect(url_for("buyer.cart"))

    # Подготовка данных для отображения
    items = []
    total = 0
    for pid, qty in cart.items():
        p = read_json(Path(PRODUCTS) / f"{pid}.json")
        if p:
            price = p.get("price", 0)
            items.append({
                "product": p,
                "qty": qty,
                "sum": price * qty
            })
            total += price * qty

    if request.method == "POST":
        # Создание заказа
        order_id = gen_id("o_")
        order_items = []
        for pid, qty in cart.items():
            p = read_json(Path(PRODUCTS) / f"{pid}.json")
            price = p.get("price", 0) if p else 0
            order_items.append({
                "product_id": pid,
                "title": p.get("title") if p else "?",
                "qty": qty,
                "price": price
            })

        order = {
            "id": order_id,
            "user_id": session["user"]["id"],
            "items": order_items,
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