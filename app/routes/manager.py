from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..utils import USERS, PRODUCTS, ORDERS, read_json, list_json, write_json, gen_id
from pathlib import Path

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
    customers = [u for u in list_json(USERS) if u.get("role")=="buyer"]
    selected = None
    orders = []
    if request.method=="POST":
        selected = request.form.get("customer_id")
        orders = [o for o in list_json(ORDERS) if o.get("user_id")==selected]
    return render_template("manager_select.html", customers=customers, selected=selected, orders=orders)

@bp.route("/catalog")
def manager_catalog():
    if "user" not in session or session["user"].get("role") not in ["manager","admin"]:
        return redirect(url_for("buyer.login"))
    products = list_json(PRODUCTS)
    return render_template("catalog.html", products=products)
