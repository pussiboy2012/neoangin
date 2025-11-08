import os
import json
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from io import BytesIO
from utils.dadata_api import get_company_by_inn
from utils.pdf_generator import html_to_pdf_bytes

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")  # для flash

# Загрузим продавца
with open("data/seller.json", encoding="utf-8") as f:
    SELLER = json.load(f)

# DaData token из переменных окружения
DADATA_TOKEN = os.environ.get("68e5b8f7ddbfa183485105918c8e28cedefad5c7")  # поставь туда свой ключ

@app.route("/", methods=["GET"])
def index():
    return render_template("form.html")

@app.route("/preview", methods=["POST"])
def preview():
    inn = request.form.get("inn")
    if not inn:
        flash("Введите ИНН покупателя")
        return redirect(url_for("index"))

    buyer = get_company_by_inn(inn, DADATA_TOKEN)
    if not buyer:
        flash("Покупатель по ИНН не найден")
        return redirect(url_for("index"))

    # Сбор позиций
    names = request.form.getlist("item_name[]")
    qtys = request.form.getlist("item_qty[]")
    prices = request.form.getlist("item_price[]")

    items = []
    for n, q, p in zip(names, qtys, prices):
        if not n:
            continue
        try:
            qf = float(q)
        except:
            qf = 0.0
        try:
            pf = float(p)
        except:
            pf = 0.0
        total = round(qf * pf, 2)
        items.append({
            "name": n,
            "qty": qf,
            "price": pf,
            "total": total
        })

    total_sum = round(sum(item["total"] for item in items), 2)

    rendered = render_template("upd_preview.html", seller=SELLER, buyer=buyer, items=items, total_sum=total_sum)
    # В шаблоне покажем кнопку Скачать — отправлять POST с html в /download
    return rendered

@app.route("/download", methods=["POST"])
def download():
    # Получаем HTML (frontend отправляет с формы)
    html = request.form.get("html")
    if not html:
        return "Нет HTML для генерации", 400
    pdf_io = html_to_pdf_bytes(html)
    pdf_io.seek(0)
    return send_file(pdf_io, as_attachment=True, download_name="UPD.pdf", mimetype="application/pdf")

# API для интеграции (будущее) — принимает JSON и возвращает PDF
@app.route("/api/generate_upd", methods=["POST"])
def api_generate_upd():
    """
    Ожидает JSON:
    {
      "buyer_inn": "7701234567",
      "items": [{"name": "...", "qty": 1, "price": 100.0}, ...],
      "extra": { ... }  # опционально
    }
    Возвращает PDF в теле ответа.
    """
    data = request.get_json(force=True)
    buyer_inn = data.get("buyer_inn")
    items = data.get("items", [])
    buyer = get_company_by_inn(buyer_inn, DADATA_TOKEN)
    if not buyer:
        return {"error": "buyer_not_found"}, 404

    # нормализуем элементы
    parsed_items = []
    for it in items:
        name = it.get("name")
        qty = float(it.get("qty", 0))
        price = float(it.get("price", 0))
        parsed_items.append({"name": name, "qty": qty, "price": price, "total": round(qty * price, 2)})
    total_sum = round(sum(it["total"] for it in parsed_items), 2)

    html = render_template("upd_preview.html", seller=SELLER, buyer=buyer, items=parsed_items, total_sum=total_sum)
    pdf_io = html_to_pdf_bytes(html)
    pdf_io.seek(0)
    return send_file(pdf_io, mimetype="application/pdf", as_attachment=True, download_name="UPD.pdf")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
