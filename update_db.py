from app import create_app
from app.models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Drop id_stock column from product-order if exists
        db.session.execute(text('ALTER TABLE "product-order" DROP COLUMN IF EXISTS id_stock'))
        db.session.commit()
        print("Column id_stock dropped from product-order (if existed)")
    except Exception as e:
        print(f"Note: Could not drop id_stock column: {e}")

    try:
        # Create stock-order table if not exists
        db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS "stock-order" (
                id_stock INT4 NOT NULL,
                id_order INT4 NOT NULL,
                count_order INT4,
                PRIMARY KEY (id_stock, id_order),
                FOREIGN KEY (id_stock) REFERENCES stocks(id_stock),
                FOREIGN KEY (id_order) REFERENCES orders(id_order)
            )
        '''))
        db.session.commit()
        print("Table stock-order created (if not existed)")
    except Exception as e:
        print(f"Note: Could not create stock-order table: {e}")

    # Create product_stock_series view
    db.session.execute(text('''
        CREATE OR REPLACE VIEW public.product_stock_series AS
         SELECT concat(p.nomenclature_product,
                CASE
                    WHEN (s.ral_stock IS NOT NULL) THEN concat(' RAL ', s.ral_stock)
                    ELSE ''::text
                END) AS nomenclature_ral,
            concat('п.', s.id_stock, ' от ', to_char((s.date_stock)::timestamp with time zone, 'DD.MM.YYYY'::text), ' до ', to_char((s.date_stock + ((p.expiration_month_product || ' months'::text))::interval), 'DD.MM.YYYY'::text)) AS series_info,
            s.count_stock AS remaining_quantity
           FROM (public.stocks s
             JOIN public.products p ON ((s.id_product = p.id_product)))
          WHERE (s.count_stock > 0);
    '''))
    db.session.commit()
    print("View product_stock_series created or replaced")
