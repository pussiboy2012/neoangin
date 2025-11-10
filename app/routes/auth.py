# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.utils.user_manager import save_user, verify_user, get_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        success, message = save_user(name, email, password)
        flash(message)

        if success:
            return redirect(url_for('auth.login'))

    return render_template('register.html', title="Регистрация")

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = verify_user(email, password)
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash('Добро пожаловать, ' + user['name'] + '!')
            return redirect(url_for('auth.profile'))
        else:
            flash('Неверный email или пароль.')

    return render_template('login.html', title="Авторизация")

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.')
    return redirect(url_for('buyer.index'))

@auth_bp.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему.')
        return redirect(url_for('auth.login'))
    return render_template('profile.html', title="Личный кабинет", user=session)
