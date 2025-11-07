from flask import render_template, request, jsonify, current_app
from flask_login import current_user
from werkzeug.exceptions import HTTPException
import traceback
from datetime import datetime
from utils.logging_config import handle_application_error, log_security_event
from functools import wraps

def init_error_handlers(app):
    """Initialize custom error handlers for the Flask application"""

    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Bad Request',
                'message': 'The request could not be understood by the server',
                'error_id': handle_application_error(app, error, {'path': request.path})
            }), 400

        return render_template('errors/400.html', error=error), 400

    @app.errorhandler(401)
    def unauthorized(error):
        # Log unauthorized access attempts
        log_security_event('UNAUTHORIZED_ACCESS', {
            'path': request.path,
            'method': request.method,
            'user_agent': request.user_agent.string if request.user_agent else None
        }, user_id=current_user.id if current_user.is_authenticated else None,
           ip_address=request.remote_addr)

        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication is required to access this resource',
                'error_id': handle_application_error(app, error, {'path': request.path})
            }), 401

        return render_template('errors/401.html', error=error), 401

    @app.errorhandler(403)
    def forbidden(error):
        # Log forbidden access attempts
        log_security_event('FORBIDDEN_ACCESS', {
            'path': request.path,
            'method': request.method,
            'user_agent': request.user_agent.string if request.user_agent else None
        }, user_id=current_user.id if current_user.is_authenticated else None,
           ip_address=request.remote_addr)

        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource',
                'error_id': handle_application_error(app, error, {'path': request.path})
            }), 403

        return render_template('errors/403.html', error=error), 403

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Not Found',
                'message': 'The requested resource was not found',
                'error_id': handle_application_error(app, error, {'path': request.path})
            }), 404

        return render_template('errors/404.html', error=error), 404

    @app.errorhandler(429)
    def ratelimit_handler(error):
        # Log rate limiting events
        log_security_event('RATE_LIMIT_EXCEEDED', {
            'path': request.path,
            'method': request.method,
            'user_agent': request.user_agent.string if request.user_agent else None
        }, user_id=current_user.id if current_user.is_authenticated else None,
           ip_address=request.remote_addr)

        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Too Many Requests',
                'message': 'Rate limit exceeded. Please try again later.',
                'error_id': handle_application_error(app, error, {'path': request.path})
            }), 429

        return render_template('errors/429.html', error=error), 429

    @app.errorhandler(500)
    def internal_error(error):
        # Log internal server errors
        error_id = handle_application_error(app, error, {
            'path': request.path,
            'method': request.method,
            'form_data': dict(request.form) if request.form else None,
            'args': dict(request.args) if request.args else None,
            'user_agent': request.user_agent.string if request.user_agent else None,
            'user_id': current_user.id if current_user.is_authenticated else None
        })

        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'error_id': error_id
            }), 500

        return render_template('errors/500.html', error=error, error_id=error_id), 500

    @app.errorhandler(502)
    def bad_gateway(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Bad Gateway',
                'message': 'The server received an invalid response',
                'error_id': handle_application_error(app, error, {'path': request.path})
            }), 502

        return render_template('errors/502.html', error=error), 502

    @app.errorhandler(503)
    def service_unavailable(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Service Unavailable',
                'message': 'The service is temporarily unavailable',
                'error_id': handle_application_error(app, error, {'path': request.path})
            }), 503

        return render_template('errors/503.html', error=error), 503

    @app.errorhandler(Exception)
    def handle_unhandled_exception(error):
        """Handle any unhandled exceptions"""
        error_id = handle_application_error(app, error, {
            'path': request.path,
            'method': request.method,
            'traceback': traceback.format_exc(),
            'user_agent': request.user_agent.string if request.user_agent else None,
            'user_id': current_user.id if current_user.is_authenticated else None
        })

        current_app.logger.error(f"Unhandled exception [{error_id}]: {str(error)}")

        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'error_id': error_id
            }), 500

        return render_template('errors/500.html', error=error, error_id=error_id), 500

def safe_execute(default_return=None, log_error=True):
    """Decorator to safely execute functions with error handling"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    error_id = handle_application_error(current_app, e, {
                        'function': func.__name__,
                        'module': func.__module__,
                        'args': str(args)[:200],  # Limit arg length
                        'kwargs': str(kwargs)[:200]  # Limit kwarg length
                    })
                    current_app.logger.error(f"Safe execute failed [{error_id}]: {str(e)}")

                if default_return is not None:
                    return default_return
                elif isinstance(e, HTTPException):
                    raise  # Re-raise HTTP exceptions
                else:
                    raise  # Re-raise other exceptions

        return wrapper
    return decorator

def validate_request_data(required_fields=None, optional_fields=None):
    """Decorator to validate request data"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                if request.is_json:
                    data = request.get_json()
                elif request.form:
                    data = request.form.to_dict()
                else:
                    data = {}

                errors = []

                # Validate required fields
                if required_fields:
                    for field in required_fields:
                        if field not in data or not data[field]:
                            errors.append(f"Field '{field}' is required")

                # Validate field types (basic validation)
                for field, value in data.items():
                    if value is None:
                        continue

                    # Add more specific validations as needed
                    if isinstance(value, str):
                        if len(value) > 10000:  # Prevent extremely long values
                            errors.append(f"Field '{field}' is too long")
                        elif value.strip() != value:  # Check for leading/trailing whitespace
                            data[field] = value.strip()

                if errors:
                    return jsonify({
                        'error': 'Validation Error',
                        'message': 'Invalid request data',
                        'errors': errors
                    }), 400

                # Add validated data to kwargs
                kwargs['validated_data'] = data

                return func(*args, **kwargs)

            except Exception as e:
                error_id = handle_application_error(current_app, e, {
                    'function': func.__name__,
                    'validation_error': True
                })

                return jsonify({
                    'error': 'Validation Error',
                    'message': 'Failed to validate request data',
                    'error_id': error_id
                }), 400

        return wrapper
    return decorator

class ErrorHandler:
    """Centralized error handling utility"""

    @staticmethod
    def log_and_return_error(message, status_code=500, error_id=None):
        """Log error and return error response"""
        if not error_id:
            error_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')

        current_app.logger.error(f"Error [{error_id}]: {message}")

        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Error',
                'message': message,
                'error_id': error_id
            }), status_code

        return message, status_code

    @staticmethod
    def handle_database_error(error, context=None):
        """Handle database-related errors"""
        error_id = handle_application_error(current_app, error, {
            'error_type': 'database_error',
            'context': context
        })

        current_app.logger.error(f"Database error [{error_id}]: {str(error)}")

        return jsonify({
            'error': 'Database Error',
            'message': 'A database error occurred. Please try again later.',
            'error_id': error_id
        }), 500

    @staticmethod
    def handle_email_error(error, context=None):
        """Handle email-related errors"""
        error_id = handle_application_error(current_app, error, {
            'error_type': 'email_error',
            'context': context
        })

        current_app.logger.error(f"Email error [{error_id}]: {str(error)}")

        return jsonify({
            'error': 'Email Service Error',
            'message': 'Failed to send email. Please try again later.',
            'error_id': error_id
        }), 500

    @staticmethod
    def handle_file_error(error, context=None):
        """Handle file-related errors"""
        error_id = handle_application_error(current_app, error, {
            'error_type': 'file_error',
            'context': context
        })

        current_app.logger.error(f"File error [{error_id}]: {str(error)}")

        return jsonify({
            'error': 'File Error',
            'message': 'A file processing error occurred.',
            'error_id': error_id
        }), 400