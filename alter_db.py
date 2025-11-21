from app import create_app
from app.models import db

app = create_app()

with app.app_context():
    # Add id_stock column to product-order table
    db.engine.execute('ALTER TABLE "product-order" ADD COLUMN id_stock INT4 REFERENCES stocks(id_stock)')
    print("Column id_stock added to product-order table")
