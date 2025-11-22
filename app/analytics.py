import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func, extract, and_, or_
from .models import db, User, Product, Stock, Analyzis, Order, ProductOrder, StockOrder
from collections import defaultdict

def get_sales_trends(start_date=None, end_date=None, category=None, user_role=None):
    """График трендов продаж с фильтрами"""
    query = db.session.query(
        Order.created_at_order.label('date'),
        func.sum(ProductOrder.count * Product.price_product).label('revenue'),
        func.count(Order.id_order).label('orders_count')
    ).join(ProductOrder, Order.id_order == ProductOrder.id_order)\
     .join(Product, ProductOrder.id_product == Product.id_product)\
     .join(User, Order.id_user == User.id_user)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    if start_date:
        query = query.filter(Order.created_at_order >= start_date)
    if end_date:
        query = query.filter(Order.created_at_order <= end_date)
    if category:
        query = query.filter(Product.category_product == category)
    if user_role:
        query = query.filter(User.role_user == user_role)

    query = query.group_by(Order.created_at_order)\
                 .order_by(Order.created_at_order)

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    df['date'] = pd.to_datetime(df['date'])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(x=df['date'], y=df['revenue'], name="Выручка",
                  line=dict(color='#2ecc71', width=3)),
        secondary_y=False,
    )

    fig.add_trace(
        go.Bar(x=df['date'], y=df['orders_count'], name="Количество заказов",
              marker_color='#3498db', opacity=0.7),
        secondary_y=True,
    )

    fig.update_layout(
        title="Тренды продаж",
        xaxis_title="Дата",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=0)
    )

    fig.update_yaxes(title_text="Выручка (руб.)", secondary_y=False, showgrid=False)
    fig.update_yaxes(title_text="Количество заказов", secondary_y=True, showgrid=False)

    return fig.to_html(full_html=False, include_plotlyjs=False)

def get_product_popularity(limit=10, start_date=None, end_date=None):
    """Популярность товаров"""
    query = db.session.query(
        Product.title_product,
        Product.category_product,
        func.sum(ProductOrder.count).label('total_sold'),
        func.sum(ProductOrder.count * Product.price_product).label('total_revenue')
    ).join(ProductOrder, Product.id_product == ProductOrder.id_product)\
     .join(Order, ProductOrder.id_order == Order.id_order)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    if start_date:
        query = query.filter(Order.created_at_order >= start_date)
    if end_date:
        query = query.filter(Order.created_at_order <= end_date)

    query = query.group_by(Product.id_product, Product.title_product, Product.category_product)\
                 .order_by(func.sum(ProductOrder.count).desc())\
                 .limit(limit)

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    fig = make_subplots(rows=1, cols=2, subplot_titles=('По количеству продаж', 'По выручке'))

    fig.add_trace(
        go.Bar(x=df['title_product'], y=df['total_sold'],
              marker_color='#e74c3c', name='Количество'),
        row=1, col=1
    )

    fig.add_trace(
        go.Bar(x=df['title_product'], y=df['total_revenue'],
              marker_color='#f39c12', name='Выручка'),
        row=1, col=2
    )

    fig.update_layout(
        title="Популярность товаров",
        showlegend=False,
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=0)
    )

    fig.update_xaxes(tickangle=45, showgrid=False)
    fig.update_yaxes(showgrid=False)

    return fig.to_html(full_html=False, include_plotlyjs=False)

def get_user_activity_metrics(start_date=None, end_date=None, role=None):
    """Метрики активности пользователей"""
    # Новые пользователи по месяцам
    user_query = db.session.query(
        extract('year', User.created_at_user).label('year'),
        extract('month', User.created_at_user).label('month'),
        func.count(User.id_user).label('new_users')
    )

    if start_date:
        user_query = user_query.filter(User.created_at_user >= start_date)
    if end_date:
        user_query = user_query.filter(User.created_at_user <= end_date)
    if role:
        user_query = user_query.filter(User.role_user == role)

    user_query = user_query.group_by(extract('year', User.created_at_user),
                                    extract('month', User.created_at_user))\
                           .order_by(extract('year', User.created_at_user),
                                    extract('month', User.created_at_user))

    user_df = pd.read_sql(user_query.statement, db.engine)

    # Активные пользователи (с заказами)
    active_query = db.session.query(
        extract('year', Order.created_at_order).label('year'),
        extract('month', Order.created_at_order).label('month'),
        func.count(func.distinct(Order.id_user)).label('active_users')
    ).join(User, Order.id_user == User.id_user)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    if start_date:
        active_query = active_query.filter(Order.created_at_order >= start_date)
    if end_date:
        active_query = active_query.filter(Order.created_at_order <= end_date)
    if role:
        active_query = active_query.filter(User.role_user == role)

    active_query = active_query.group_by(extract('year', Order.created_at_order),
                                        extract('month', Order.created_at_order))\
                               .order_by(extract('year', Order.created_at_order),
                                        extract('month', Order.created_at_order))

    active_df = pd.read_sql(active_query.statement, db.engine)

    if user_df.empty and active_df.empty:
        return None

    fig = go.Figure()

    if not user_df.empty:
        user_df['date'] = pd.to_datetime(user_df[['year', 'month']].assign(day=1))
        fig.add_trace(
            go.Scatter(x=user_df['date'], y=user_df['new_users'],
                      mode='lines+markers', name='Новые пользователи',
                      line=dict(color='#27ae60', width=3))
        )

    if not active_df.empty:
        active_df['date'] = pd.to_datetime(active_df[['year', 'month']].assign(day=1))
        fig.add_trace(
            go.Scatter(x=active_df['date'], y=active_df['active_users'],
                      mode='lines+markers', name='Активные пользователи',
                      line=dict(color='#3498db', width=3))
        )

    fig.update_layout(
        title="Активность пользователей",
        xaxis_title="Месяц",
        yaxis_title="Количество пользователей",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=0)
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)

def get_stock_levels(product_id=None, ral=None):
    """Уровни запасов"""
    query = db.session.query(
        Product.title_product,
        Stock.ral_stock,
        Stock.count_stock,
        Stock.date_stock,
        Product.nomenclature_product
    ).join(Product, Stock.id_product == Product.id_product)\
     .filter(Stock.count_stock > 0)

    if product_id:
        query = query.filter(Stock.id_product == product_id)
    if ral:
        query = query.filter(Stock.ral_stock == ral)

    query = query.order_by(Stock.count_stock.desc())

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    # Группировка по товарам
    product_totals = df.groupby('title_product')['count_stock'].sum().reset_index()
    product_totals = product_totals.sort_values('count_stock', ascending=True)

    fig = make_subplots(rows=1, cols=2, subplot_titles=('По товарам', 'По RAL цветам'))

    # График по товарам
    fig.add_trace(
        go.Bar(y=product_totals['title_product'], x=product_totals['count_stock'],
              orientation='h', marker_color='#9b59b6', name='Количество'),
        row=1, col=1
    )

    # График по RAL цветам
    if 'ral_stock' in df.columns and not df['ral_stock'].isna().all():
        ral_totals = df.groupby('ral_stock')['count_stock'].sum().reset_index()
        ral_totals = ral_totals.sort_values('count_stock', ascending=True)

        fig.add_trace(
            go.Bar(y=ral_totals['ral_stock'], x=ral_totals['count_stock'],
                  orientation='h', marker_color='#e67e22', name='Количество'),
            row=1, col=2
        )

    fig.update_layout(
        title="Уровни запасов",
        showlegend=False,
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=0)
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)

    return fig.to_html(full_html=False, include_plotlyjs=False)

def get_order_status_distribution(start_date=None, end_date=None):
    """Распределение статусов заказов"""
    query = db.session.query(
        Order.status_order,
        func.count(Order.id_order).label('count')
    )

    if start_date:
        query = query.filter(Order.created_at_order >= start_date)
    if end_date:
        query = query.filter(Order.created_at_order <= end_date)

    query = query.group_by(Order.status_order)

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    # Перевод статусов на русский
    status_translation = {
        'pending_moderation': 'На модерации',
        'approved': 'Одобрен',
        'completed': 'Выполнен',
        'cancelled': 'Отменен'
    }

    df['status_ru'] = df['status_order'].map(status_translation)

    colors = ['#f39c12', '#27ae60', '#3498db', '#e74c3c']

    fig = go.Figure(data=[go.Pie(
        labels=df['status_ru'],
        values=df['count'],
        marker_colors=colors,
        textinfo='label+percent',
        insidetextorientation='radial'
    )])

    fig.update_layout(
        title="Распределение статусов заказов",
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=0)
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)

def get_revenue_analysis(start_date=None, end_date=None, group_by='month'):
    """Анализ выручки"""
    if group_by == 'month':
        date_func = func.date_trunc('month', Order.created_at_order)
    elif group_by == 'week':
        date_func = func.date_trunc('week', Order.created_at_order)
    else:
        date_func = func.date_trunc('day', Order.created_at_order)

    query = db.session.query(
        date_func.label('period'),
        func.sum(ProductOrder.count * Product.price_product).label('revenue'),
        func.count(func.distinct(Order.id_order)).label('orders'),
        func.avg(ProductOrder.count * Product.price_product).label('avg_order_value')
    ).join(ProductOrder, Order.id_order == ProductOrder.id_order)\
     .join(Product, ProductOrder.id_product == Product.id_product)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    if start_date:
        query = query.filter(Order.created_at_order >= start_date)
    if end_date:
        query = query.filter(Order.created_at_order <= end_date)

    query = query.group_by(date_func).order_by(date_func)

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    df['period'] = pd.to_datetime(df['period'])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(x=df['period'], y=df['revenue'], name="Выручка",
              marker_color='#2ecc71'),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(x=df['period'], y=df['avg_order_value'], name="Средний чек",
                  mode='lines+markers', line=dict(color='#e74c3c', width=3)),
        secondary_y=True,
    )

    fig.update_layout(
        title=f"Анализ выручки (группировка по {group_by})",
        xaxis_title="Период",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    fig.update_yaxes(title_text="Выручка (руб.)", secondary_y=False)
    fig.update_yaxes(title_text="Средний чек (руб.)", secondary_y=True)

    return fig.to_html(full_html=False, include_plotlyjs=False)

def get_analyzis_visualization(product_id=None, metric_x='glitter', metric_y='viskosity'):
    """Визуализация данных анализа"""
    query = db.session.query(
        Analyzis.glitter,
        Analyzis.viskosity,
        Analyzis.delta_e,
        Analyzis.delta_l,
        Analyzis.delta_a,
        Analyzis.delta_b,
        Analyzis.drying_time,
        Analyzis.peak_metal_temperature,
        Analyzis.thickness_for_soil,
        Analyzis.adhesion,
        Analyzis.solvent_resistance,
        Analyzis.visual_flat_control,
        Analyzis.appearance,
        Analyzis.number_of_batch_samples,
        Analyzis.degree_of_grinding,
        Analyzis.solids_by_volume,
        Analyzis.ground,
        Analyzis.mass_fraction,
        Product.title_product
    ).join(Stock, Analyzis.id_stock == Stock.id_stock)\
     .join(Product, Stock.id_product == Product.id_product)

    if product_id:
        query = query.filter(Stock.id_product == product_id)

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    # Очистка данных от None
    df = df.dropna(subset=[metric_x, metric_y])

    if df.empty:
        return None

    fig = px.scatter(df, x=metric_x, y=metric_y, color='title_product',
            title=f"Анализ качества: {metric_x} vs {metric_y}",
            labels={metric_x: metric_x, metric_y: metric_y})

    fig.update_layout(
        xaxis_title=metric_x,
        yaxis_title=metric_y,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        autosize=True,
        margin=dict(l=0, r=0, t=50, b=0)
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)
        
def get_dashboard_metrics():
    """Метрики для дашборда"""
    # Общая выручка
    revenue_query = db.session.query(
        func.sum(ProductOrder.count * Product.price_product).label('total_revenue')
    ).join(Order, ProductOrder.id_order == Order.id_order)\
     .join(Product, ProductOrder.id_product == Product.id_product)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    revenue = revenue_query.scalar() or 0

    # Количество заказов
    orders_count = Order.query.filter(Order.status_order.in_(['approved', 'completed'])).count()

    # Активные пользователи
    active_users = User.query.filter(User.role_user == 'buyer').count()

    # Популярные товары
    popular_query = db.session.query(
        Product.title_product,
        func.sum(ProductOrder.count).label('total_sold')
    ).join(ProductOrder, Product.id_product == ProductOrder.id_product)\
     .join(Order, ProductOrder.id_order == Order.id_order)\
     .filter(Order.status_order.in_(['approved', 'completed']))\
     .group_by(Product.id_product, Product.title_product)\
     .order_by(func.sum(ProductOrder.count).desc())\
     .limit(5)

    popular_products = pd.read_sql(popular_query.statement, db.engine)

    # Заказы за последний месяц
    last_month = datetime.now() - timedelta(days=30)
    orders_this_month = Order.query.filter(
        Order.created_at_order >= last_month,
        Order.status_order.in_(['approved', 'completed'])
    ).count()

    # Средний чек
    avg_order_query = db.session.query(
        func.avg(ProductOrder.count * Product.price_product).label('avg_order')
    ).join(Order, ProductOrder.id_order == Order.id_order)\
     .join(Product, ProductOrder.id_product == Product.id_product)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    avg_order_value = avg_order_query.scalar() or 0

    return {
        'total_revenue': float(revenue),
        'orders_count': orders_count,
        'active_users': active_users,
        'popular_products': popular_products.to_dict('records') if not popular_products.empty else [],
        'orders_this_month': orders_this_month,
        'avg_order_value': float(avg_order_value)
    }
