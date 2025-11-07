from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_migrate import Migrate
from flask_login import LoginManager
from config import config
from utils.logging_config import setup_logging
from utils.error_handlers import init_error_handlers
import os

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Setup logging
    loggers = setup_logging(app)
    app.loggers = loggers

    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Initialize error handlers
    init_error_handlers(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.campaigns import campaigns_bp
    from routes.tracking import tracking_bp
    from routes.analytics import analytics_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(campaigns_bp, url_prefix='/campaigns')
    app.register_blueprint(tracking_bp, url_prefix='/track')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    # Main route redirects to dashboard
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('dashboard.index'))

    # Health check endpoint
    @app.route('/health')
    def health_check():
        from flask import jsonify
        return jsonify({
            'status': 'healthy',
            'timestamp': os.environ.get('DEPLOY_TIME', 'development'),
            'version': '1.0.0'
        })

    # Security headers middleware
    @app.after_request
    def add_security_headers(response):
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'"
        return response

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from database.models import User
        return User.query.get(int(user_id))

    # Create database tables and sample data
    with app.app_context():
        try:
            from database.models import User, Template, Campaign, Target, CampaignTarget, EmailEvent, AuditLog
            db.create_all()

            # Create sample data if database is empty
            from database.models import create_sample_data
            if not User.query.first():
                create_sample_data()
                app.logger.info("Sample data created successfully")
            else:
                app.logger.info("Database already contains data")

        except Exception as e:
            app.logger.error(f"Database initialization error: {str(e)}")
            # In production, you might want to handle this more gracefully
            if config_name != 'development':
                raise

    # Log application startup
    app.logger.info(f"Phishing Simulation Platform started successfully in {config_name} mode")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)