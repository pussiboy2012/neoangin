import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func, extract
from .models import db, User, Product, Stock, Analyzis, Order, ProductOrder

# Define a consistent color palette based on CSS variables
COLORS = {
    'primary': '#2c3e50',  # dark blue
    'accent': '#e74c3c',   # red
    'info': '#3498db',     # blue
    'success': '#27ae60',  # green
    'warning': '#f39c12',  # orange
    'purple': '#9b59b6',
    'orange': '#e67e22'
}

def get_sales_trends(start_date=None, end_date=None, category=None, user_role=None):
    """График трендов продаж с фильтрами, возвращает данные для chart.js"""
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
    labels = df['date'].dt.strftime('%Y-%m-%d').tolist()
    revenue_data = df['revenue'].tolist()
    orders_count_data = df['orders_count'].tolist()

    data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Выручка',
                'data': revenue_data,
                'borderColor': COLORS['success'],
                'backgroundColor': COLORS['success'],
                'yAxisID': 'y',
                'type': 'line',
                'fill': False,
                'tension': 0.3,
                'pointRadius': 5
            },
            {
                'label': 'Количество заказов',
                'data': orders_count_data,
                'backgroundColor': COLORS['info'],
                'yAxisID': 'y1',
                'type': 'bar',
                'opacity': 0.8
            }
        ]
    }
    options = {
        'responsive': True,
        'interaction': {
            'mode': 'index',
            'intersect': False
        },
        'stacked': False,
        'plugins': {
            'title': {
                'display': True,
                'text': 'Тренды продаж',
                'font': {'size': 24, 'family': 'Arial', 'color': COLORS['primary']}
            }
        },
        'scales': {
            'y': {
                'type': 'linear',
                'display': True,
                'position': 'left',
                'title': {
                    'display': True,
                    'text': 'Выручка (руб.)'
                },
                'grid': {
                    'display': True,
                    'color': 'rgba(0,0,0,0.05)'
                }
            },
            'y1': {
                'type': 'linear',
                'display': True,
                'position': 'right',
                'title': {
                    'display': True,
                    'text': 'Количество заказов'
                },
                'grid': {
                    'drawOnChartArea': False
                }
            },
            'x': {
                'grid': {
                    'display': True,
                    'color': 'rgba(0,0,0,0.05)'
                }
            }
        }
    }
    return {'data': data, 'options': options}

def get_product_popularity(limit=10, start_date=None, end_date=None):
    """Популярность товаров, возвращает данные для Chart.js"""
    query = db.session.query(
        Product.title_product,
        func.sum(ProductOrder.count).label('total_sold'),
        func.sum(ProductOrder.count * Product.price_product).label('total_revenue')
    ).join(ProductOrder, Product.id_product == ProductOrder.id_product)\
     .join(Order, ProductOrder.id_order == Order.id_order)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    if start_date:
        query = query.filter(Order.created_at_order >= start_date)
    if end_date:
        query = query.filter(Order.created_at_order <= end_date)

    query = query.group_by(Product.id_product, Product.title_product)\
                 .order_by(func.sum(ProductOrder.count).desc())\
                 .limit(limit)

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    labels = df['title_product'].tolist()
    sold_data = df['total_sold'].tolist()
    revenue_data = df['total_revenue'].tolist()

    data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Количество продаж',
                'data': sold_data,
                'backgroundColor': COLORS['accent'],
                'type': 'bar'
            },
            {
                'label': 'Выручка',
                'data': revenue_data,
                'backgroundColor': COLORS['warning'],
                'type': 'bar'
            }
        ]
    }
    options = {
        'responsive': True,
        'plugins': {
            'title': {
                'display': True,
                'text': 'Популярность товаров',
                'font': {'size': 24, 'family': 'Arial', 'color': COLORS['primary']}
            },
            'legend': {
                'display': True,
                'position': 'top'
            }
        },
        'scales': {
            'x': {
                'ticks': {'autoSkip': False}
            },
            'y': {
                'beginAtZero': True,
                'grid': {
                    'color': 'rgba(0,0,0,0.05)'
                }
            }
        }
    }
    return {'data': data, 'options': options}

def get_user_activity_metrics(start_date=None, end_date=None, role=None):
    """Метрики активности пользователей, возвращает данные для Chart.js"""
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

    # Construct labels as months YYYY-MM
    def format_year_month(row):
        return f"{int(row['year'])}-{int(row['month']):02d}"

    user_labels = user_df.apply(format_year_month, axis=1).tolist() if not user_df.empty else []
    active_labels = active_df.apply(format_year_month, axis=1).tolist() if not active_df.empty else []

    labels = sorted(set(user_labels) | set(active_labels))

    def get_series(df, label_col, value_col):
        series = []
        for label in labels:
            value = df[df.apply(format_year_month, axis=1) == label][value_col]
            series.append(int(value.iloc[0]) if not value.empty else 0)
        return series

    new_users_data = get_series(user_df, 'year', 'new_users') if not user_df.empty else [0]*len(labels)
    active_users_data = get_series(active_df, 'year', 'active_users') if not active_df.empty else [0]*len(labels)

    data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Новые пользователи',
                'data': new_users_data,
                'borderColor': COLORS['success'],
                'backgroundColor': COLORS['success'],
                'fill': False,
                'tension': 0.3,
                'pointRadius': 5,
                'type': 'line'
            },
            {
                'label': 'Активные пользователи',
                'data': active_users_data,
                'borderColor': COLORS['info'],
                'backgroundColor': COLORS['info'],
                'fill': False,
                'tension': 0.3,
                'pointRadius': 5,
                'type': 'line'
            }
        ]
    }
    options = {
        'responsive': True,
        'plugins': {
            'title': {
                'display': True,
                'text': 'Активность пользователей',
                'font': {'size': 24, 'family': 'Arial', 'color': COLORS['primary']}
            },
            'legend': {
                'display': True,
                'position': 'top'
            }
        },
        'scales': {
            'x': {'grid': {'color': 'rgba(0,0,0,0.05)'}},
            'y': {
                'beginAtZero': True,
                'grid': {'color': 'rgba(0,0,0,0.05)'}
            }
        }
    }
    return {'data': data, 'options': options}

def get_stock_levels(product_id=None, ral=None):
    """Уровни запасов, возвращает данные для Chart.js"""
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

    # Group by products
    product_totals = df.groupby('title_product')['count_stock'].sum().reset_index()
    product_totals = product_totals.sort_values('count_stock', ascending=True)

    # Group by ral_stock
    ral_totals = None
    if 'ral_stock' in df.columns and not df['ral_stock'].isna().all():
        ral_totals = df.groupby('ral_stock')['count_stock'].sum().reset_index()
        ral_totals = ral_totals.sort_values('count_stock', ascending=True)

    data = {
        'labels_product': product_totals['title_product'].tolist(),
        'data_product': product_totals['count_stock'].tolist(),
        'labels_ral': ral_totals['ral_stock'].tolist() if ral_totals is not None else [],
        'data_ral': ral_totals['count_stock'].tolist() if ral_totals is not None else []
    }

    # For Chart.js, we can return two separate datasets or separate charts on front-end
    datasets = []

    if data['labels_product']:
        datasets.append({
            'label': 'По товарам',
            'data': data['data_product'],
            'backgroundColor': COLORS['purple'],
            'type': 'bar',
            'labels': data['labels_product'],
        })

    if data['labels_ral']:
        datasets.append({
            'label': 'По RAL цветам',
            'data': data['data_ral'],
            'backgroundColor': COLORS['orange'],
            'type': 'bar',
            'labels': data['labels_ral'],
        })

    options = {
        'responsive': True,
        'plugins': {
            'title': {
                'display': True,
                'text': 'Уровни запасов',
                'font': {'size': 24, 'family': 'Arial', 'color': COLORS['primary']}
            },
            'legend': {'display': False}
        },
        'scales': {
            'x': {'grid': {'color': 'rgba(0,0,0,0.05)'}},
            'y': {
                'beginAtZero': True,
                'grid': {'color': 'rgba(0,0,0,0.05)'}
            }
        }
    }

    return {'datasets': datasets, 'options': options}

def get_order_status_distribution(start_date=None, end_date=None):
    """Распределение статусов заказов, возвращает данные для Chart.js"""
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

    status_translation = {
        'pending_moderation': 'На модерации',
        'approved': 'Одобрен',
        'completed': 'Выполнен',
        'cancelled': 'Отменен'
    }

    labels = df['status_order'].map(status_translation).tolist()
    data_values = df['count'].tolist()
    colors = [COLORS['warning'], COLORS['success'], COLORS['info'], COLORS['accent']]

    data = {
        'labels': labels,
        'datasets': [{
            'data': data_values,
            'backgroundColor': colors
        }]
    }

    options = {
        'responsive': True,
        'plugins': {
            'title': {
                'display': True,
                'text': 'Распределение статусов заказов',
                'font': {'size': 24, 'family': 'Arial', 'color': COLORS['primary']}
            },
            'legend': {'display': True, 'position': 'top'}
        }
    }

    return {'data': data, 'options': options}

def get_revenue_analysis(start_date=None, end_date=None, group_by='month'):
    """Анализ выручки, возвращает данные для Chart.js"""
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
    labels = df['period'].dt.strftime('%Y-%m-%d').tolist()
    revenue_data = df['revenue'].tolist()
    avg_order_data = df['avg_order_value'].tolist()

    data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Выручка',
                'data': revenue_data,
                'backgroundColor': COLORS['success'],
                'type': 'bar'
            },
            {
                'label': 'Средний чек',
                'data': avg_order_data,
                'borderColor': COLORS['accent'],
                'backgroundColor': COLORS['accent'],
                'fill': False,
                'tension': 0.3,
                'pointRadius': 5,
                'type': 'line'
            }
        ]
    }

    options = {
        'responsive': True,
        'plugins': {
            'title': {
                'display': True,
                'text': f"Анализ выручки (группировка по {group_by})",
                'font': {'size': 24, 'family': 'Arial', 'color': COLORS['primary']}
            },
            'legend': {'display': True, 'position': 'top'}
        },
        'scales': {
            'x': {'grid': {'color': 'rgba(0,0,0,0.05)'}},
            'y': {
                'beginAtZero': True,
                'grid': {'color': 'rgba(0,0,0,0.05)'}
            }
        }
    }

    return {'data': data, 'options': options}

def get_analyzis_visualization(product_id=None, metric_x='glitter', metric_y='viskosity'):
    """Визуализация данных анализа, возвращает данные для Chart.js"""
    query = db.session.query(
        Analyzis.glitter,
        Analyzis.viskosity,
        Product.title_product
    ).join(Stock, Analyzis.id_stock == Stock.id_stock)\
     .join(Product, Stock.id_product == Product.id_product)

    if product_id:
        query = query.filter(Stock.id_product == product_id)

    df = pd.read_sql(query.statement, db.engine)

    if df.empty:
        return None

    df = df.dropna(subset=[metric_x, metric_y])

    if df.empty:
        return None

    labels = df['title_product'].tolist()
    x_data = df[metric_x].tolist()
    y_data = df[metric_y].tolist()

    data = {
        'labels': labels,
        'datasets': [{
            'label': f'{metric_y} vs {metric_x}',
            'data': [{'x': x_data[i], 'y': y_data[i]} for i in range(len(x_data))],
            'backgroundColor': COLORS['primary'],
            'showLine': False,
            'type': 'scatter'
        }]
    }

    options = {
        'responsive': True,
        'plugins': {
            'title': {
                'display': True,
                'text': f"Анализ качества: {metric_x} vs {metric_y}",
                'font': {'size': 24, 'family': 'Arial', 'color': COLORS['primary']}
            },
            'legend': {'display': False}
        },
        'scales': {
            'x': {
                'title': {'display': True, 'text': metric_x},
                'grid': {'color': 'rgba(0,0,0,0.05)'}
            },
            'y': {
                'title': {'display': True, 'text': metric_y},
                'grid': {'color': 'rgba(0,0,0,0.05)'}
            }
        }
    }

    return {'data': data, 'options': options}

def get_dashboard_metrics():
    """Метрики для дашборда"""
    revenue_query = db.session.query(
        func.sum(ProductOrder.count * Product.price_product).label('total_revenue')
    ).join(Order, ProductOrder.id_order == Order.id_order)\
     .join(Product, ProductOrder.id_product == Product.id_product)\
     .filter(Order.status_order.in_(['approved', 'completed']))

    revenue = revenue_query.scalar() or 0

    orders_count = Order.query.filter(Order.status_order.in_(['approved', 'completed'])).count()

    active_users = User.query.filter(User.role_user == 'buyer').count()

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

    last_month = datetime.now() - timedelta(days=30)
    orders_this_month = Order.query.filter(
        Order.created_at_order >= last_month,
        Order.status_order.in_(['approved', 'completed'])
    ).count()

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
