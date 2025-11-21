from .models import db, User, Product, Stock, Order, ProductOrder, Analyzis
from datetime import datetime
import hashlib
import secrets

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(8)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def verify_password(password, hashed, salt):
    test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return test_hash == hashed

def get_all_users():
    return User.query.all()

def get_user_by_email(email):
    return User.query.filter_by(email_user=email).first()

def get_user_by_id(user_id):
    return User.query.get(user_id)

def create_user(email, fullname, inn, company_name, phone, password, role='buyer'):
    hashed, salt = hash_password(password)
    user = User(
        email_user=email,
        fullname_user=fullname,
        inn_user=inn,
        company_name_user=company_name,
        phone_user=phone,
        password_hash_user=hashed + ':' + salt,  # store hash:salt
        role_user=role,
        created_at_user=datetime.utcnow().date(),
        company_verified_user=True  # assume verified for now
    )
    db.session.add(user)
    db.session.commit()
    return user

def get_all_products():
    return Product.query.all()

def get_product_by_id(product_id):
    return Product.query.get(product_id)

def create_product(title, price, category, description, img_path, expiration_month, nomenclature):
    product = Product(
        title_product=title,
        price_product=price,
        created_at_product=datetime.utcnow().date(),
        category_product=category,
        description_product=description,
        img_path_product=img_path,
        expiration_month_product=expiration_month,
        nomenclature_product=nomenclature
    )
    db.session.add(product)
    db.session.commit()
    return product

def get_stock_by_product_id(product_id):
    return Stock.query.filter_by(id_product=product_id).first()

def update_stock(product_id, qty, ral=None):
    stock = get_stock_by_product_id(product_id)
    if stock:
        stock.count_stock = qty
        if ral:
            stock.ral_stock = ral
        stock.date_stock = datetime.utcnow().date()
    else:
        stock = Stock(
            id_product=product_id,
            count_stock=qty,
            ral_stock=ral,
            date_stock=datetime.utcnow().date()
        )
        db.session.add(stock)
    db.session.commit()
    return stock

def get_all_orders():
    return Order.query.all()

def get_orders_by_user(user_id):
    return Order.query.filter_by(id_user=user_id).all()

def get_order_by_id(order_id):
    return Order.query.get(order_id)

def create_order(user_id, items, status='pending_moderation'):
    order = Order(
        id_user=user_id,
        status_order=status,
        created_at_order=datetime.utcnow().date()
    )
    db.session.add(order)
    db.session.flush()  # to get order.id_order

    for item in items:
        po = ProductOrder(
            id_product=item['product_id'],
            id_order=order.id_order,
            count=item['qty'],
            ral=item.get('ral'),
            creating_date=datetime.utcnow().date()
        )
        db.session.add(po)

    db.session.commit()
    return order

def update_order_status(order_id, status):
    order = get_order_by_id(order_id)
    if order:
        order.status_order = status
        order.updated_at_order = datetime.utcnow().date()
        db.session.commit()
    return order

def get_analyzis_by_stock(stock_id):
    return Analyzis.query.filter_by(id_stock=stock_id).first()

def create_or_update_analyzis(stock_id, **kwargs):
    analyzis = get_analyzis_by_stock(stock_id)
    if analyzis:
        for key, value in kwargs.items():
            setattr(analyzis, key, value)
    else:
        analyzis = Analyzis(id_stock=stock_id, **kwargs)
        db.session.add(analyzis)
    db.session.commit()
    return analyzis

def verify_user(email, password):
    user = get_user_by_email(email)
    if user:
        password_hash = user.password_hash_user
        if ':' in password_hash:
            # New format with salt
            hashed, salt = password_hash.split(':')
            if verify_password(password, hashed, salt):
                return user
        else:
            # Old format without salt
            if verify_password(password, password_hash, ''):
                return user
    return None
