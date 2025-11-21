from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..db_helpers import get_all_users, get_all_products, get_orders_by_user, get_all_orders

bp = Blueprint("manager", __name__, template_folder="../templates")

@bp.route("/")
def manager_index():
    # simple auth for demo: check session role
    if "user" not in session or session["user"].get("role") not in ["manager","admin"]:
        flash("Требуется вход менеджера")
        return redirect(url_for("buyer.login"))
    return render_template("manager_index.html")

@bp.route("/select_customer", methods=["GET","POST"])
def select_customer():
    if "user" not in session or session["user"].get("role") not in ["manager","admin"]:
        return redirect(url_for("buyer.login"))
    customers = [u for u in get_all_users() if u.role_user == "buyer"]
    selected = None
    orders = []
    if request.method=="POST":
        selected = request.form.get("customer_id")
        orders = get_orders_by_user(int(selected))
    return render_template("manager_select.html", customers=customers, selected=selected, orders=orders)

@bp.route("/catalog")
def manager_catalog():
    if "user" not in session or session["user"].get("role") not in ["manager","admin"]:
        return redirect(url_for("buyer.login"))
    products = get_all_products()
    return render_template("catalog.html", products=products)
