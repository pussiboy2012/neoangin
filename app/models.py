from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id_user = db.Column(db.Integer, primary_key=True)
    email_user = db.Column(db.String(255), nullable=False, unique=True)
    fullname_user = db.Column(db.String(255), nullable=False)
    inn_user = db.Column(db.String(12), nullable=False)
    company_name_user = db.Column(db.String(255), nullable=False)
    phone_user = db.Column(db.String(16), nullable=False)
    password_hash_user = db.Column(db.String(255), nullable=False)
    role_user = db.Column(db.String(7), nullable=False)
    created_at_user = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    company_verified_user = db.Column(db.Boolean, nullable=False, default=False)

    orders = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id_product = db.Column(db.Integer, primary_key=True)
    title_product = db.Column(db.String(255), nullable=False)
    price_product = db.Column(db.Numeric, nullable=False)
    created_at_product = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    category_product = db.Column(db.String(255), nullable=False)
    description_product = db.Column(db.Text, nullable=False)
    img_path_product = db.Column(db.String(255), nullable=True)
    expiration_month_product = db.Column(db.Integer, nullable=False)
    nomenclature_product = db.Column(db.String(255), nullable=False)

    stocks = db.relationship('Stock', backref='product', lazy=True)
    order_items = db.relationship('ProductOrder', backref='product', lazy=True)

class Stock(db.Model):
    __tablename__ = 'stocks'
    id_stock = db.Column(db.Integer, primary_key=True)
    id_product = db.Column(db.Integer, db.ForeignKey('products.id_product'), nullable=False)
    id_analyzis = db.Column(db.Integer, db.ForeignKey('analyzis.id_analyzis'), nullable=True)
    count_stock = db.Column(db.Integer, nullable=False)
    ral_stock = db.Column(db.String(4), nullable=True)
    date_stock = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)

class Analyzis(db.Model):
    __tablename__ = 'analyzis'
    id_analyzis = db.Column(db.Integer, primary_key=True)
    id_stock = db.Column(db.Integer, db.ForeignKey('stocks.id_stock'), nullable=False)
    glitter = db.Column(db.Float, nullable=True)
    viskosity = db.Column(db.Float, nullable=True)
    delta_e = db.Column(db.Float, nullable=True)
    delta_l = db.Column(db.Float, nullable=True)
    delta_a = db.Column(db.Float, nullable=True)
    delta_b = db.Column(db.Float, nullable=True)
    drying_time = db.Column(db.Float, nullable=True)
    peak_metal_temperature = db.Column(db.Float, nullable=True)
    thickness_for_soil = db.Column(db.Float, nullable=True)
    adhesion = db.Column(db.Float, nullable=True)
    solvent_resistance = db.Column(db.Float, nullable=True)
    visual_flat_control = db.Column(db.Text, nullable=True)
    appearance = db.Column(db.Text, nullable=True)
    number_of_batch_samples = db.Column(db.Integer, nullable=True)
    degree_of_grinding = db.Column(db.Float, nullable=True)
    solids_by_volume = db.Column(db.Float, nullable=True)
    ground = db.Column(db.Float, nullable=True)
    mass_fraction = db.Column(db.Float, nullable=True)

class Order(db.Model):
    __tablename__ = 'orders'
    id_order = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('users.id_user'), nullable=False)
    date_shipment = db.Column(db.Date, nullable=True)
    cancelation_reason_order = db.Column(db.Text, nullable=True)
    status_order = db.Column(db.String(255), nullable=False)
    created_at_order = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    updated_at_order = db.Column(db.Date, nullable=True)

    order_items = db.relationship('ProductOrder', backref='order', lazy=True)
    stock_order_items = db.relationship('StockOrder', backref='order', lazy=True)

class ProductOrder(db.Model):
    __tablename__ = 'product-order'
    id_product = db.Column(db.Integer, db.ForeignKey('products.id_product'), primary_key=True)
    id_order = db.Column(db.Integer, db.ForeignKey('orders.id_order'), primary_key=True)
    count = db.Column(db.Integer, nullable=False)
    ral = db.Column(db.String(4), nullable=True)
    creating_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)

class StockOrder(db.Model):
    __tablename__ = 'stock-order'
    id_stock = db.Column(db.Integer, db.ForeignKey('stocks.id_stock'), primary_key=True)
    id_order = db.Column(db.Integer, db.ForeignKey('orders.id_order'), primary_key=True)
    count_order = db.Column(db.Integer, nullable=True)

    stock = db.relationship('Stock', backref='stock_orders', lazy=True)
