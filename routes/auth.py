from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import db
from database.models import User
from utils.validators import LoginForm, RegistrationForm
from utils.security import log_audit, is_safe_url
from datetime import datetime, timezone

auth_bp = Blueprint('auth', __name__)

# Flask-Login setup
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    flash('You must be logged in to access this page.', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember.data)
            user.last_login = datetime.now(timezone.utc)

            # Log the login event
            log_audit('USER_LOGIN', 'user', user.id)

            db.session.commit()

            # Handle next parameter for redirects
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)

            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            # Log failed login attempt
            if user:
                log_audit('LOGIN_FAILED', 'user', user.id, {'reason': 'invalid_password'})
            else:
                log_audit('LOGIN_FAILED', None, None, {'username': form.username.data, 'reason': 'user_not_found'})

            flash('Invalid username or password', 'danger')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    # Check if registration is allowed (can be disabled in production)
    from flask import current_app
    if current_app.config.get('DISABLE_REGISTRATION', False):
        flash('User registration is disabled. Please contact an administrator.', 'warning')
        return redirect(url_for('auth.login'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            is_admin=False  # First user can be made admin manually
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # Log registration
        log_audit('USER_REGISTER', 'user', user.id, {'email': user.email})

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    # Log the logout event
    log_audit('USER_LOGOUT', 'user', current_user.id)

    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('auth/profile.html')

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    from flask_wtf import FlaskForm
    from wtforms import PasswordField, SubmitField
    from wtforms.validators import DataRequired, EqualTo, Length

    class ChangePasswordForm(FlaskForm):
        current_password = PasswordField('Current Password', validators=[DataRequired()])
        new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
        confirm_password = PasswordField('Confirm New Password', validators=[
            DataRequired(), EqualTo('new_password', message='Passwords must match')
        ])
        submit = SubmitField('Change Password')

    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()

            # Log password change
            log_audit('PASSWORD_CHANGED', 'user', current_user.id)

            flash('Your password has been changed successfully.', 'success')
            return redirect(url_for('auth.profile'))
        else:
            flash('Current password is incorrect.', 'danger')

    return render_template('auth/change_password.html', form=form)