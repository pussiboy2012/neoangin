from app import create_app
from app.models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Drop id_stock column from product-order
    db.session.execute(text('ALTER TABLE "product-order" DROP COLUMN id_stock'))
    db.session.commit()
    print("Column id_stock dropped from product-order")

    # Create stock-order table
    db.session.execute(text('''CREATE TABLE "stock-order" (
        id_stock INT4 NOT NULL,
        id_order INT4 NOT NULL,
        count_order INT4,
        PRIMARY KEY (id_stock, id_order),
        FOREIGN KEY (id_stock) REFERENCES stocks(id_stock),
        FOREIGN KEY (id_order) REFERENCES orders(id_order)
    )'''))
    db.session.commit()
    print("Table stock-order created")
