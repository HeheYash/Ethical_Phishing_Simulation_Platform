import logging
import logging.handlers
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
import sys

def setup_logging(app):
    """Configure comprehensive logging for the application"""

    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure log levels based on environment
    if app.config.get('TESTING', False):
        log_level = logging.WARNING
    elif app.config.get('DEBUG', False):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s [%(filename)s:%(lineno)d] - %(message)s'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s %(levelname)s - %(message)s'
    )

    # Remove existing handlers
    app.logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    app.logger.addHandler(console_handler)

    # Application log file
    app_log_file = os.path.join(log_dir, 'application.log')
    app_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    app_handler.setLevel(log_level)
    app_handler.setFormatter(detailed_formatter)
    app.logger.addHandler(app_handler)

    # Error log file
    error_log_file = os.path.join(log_dir, 'errors.log')
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    app.logger.addHandler(error_handler)

    # Security events log
    security_log_file = os.path.join(log_dir, 'security_events.log')
    security_handler = RotatingFileHandler(
        security_log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=10
    )
    security_handler.setLevel(logging.INFO)
    security_handler.setFormatter(detailed_formatter)

    # Create security logger
    security_logger = logging.getLogger('security')
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.INFO)

    # Email sending log
    email_log_file = os.path.join(log_dir, 'email_sends.log')
    email_handler = RotatingFileHandler(
        email_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=3
    )
    email_handler.setLevel(logging.INFO)
    email_handler.setFormatter(detailed_formatter)

    # Create email logger
    email_logger = logging.getLogger('email')
    email_logger.addHandler(email_handler)
    email_logger.setLevel(logging.INFO)

    # Campaign activity log
    campaign_log_file = os.path.join(log_dir, 'campaign_activity.log')
    campaign_handler = RotatingFileHandler(
        campaign_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    campaign_handler.setLevel(logging.INFO)
    campaign_handler.setFormatter(detailed_formatter)

    # Create campaign logger
    campaign_logger = logging.getLogger('campaign')
    campaign_logger.addHandler(campaign_handler)
    campaign_logger.setLevel(logging.INFO)

    # Set application logger level
    app.logger.setLevel(log_level)

    # Log application startup
    app.logger.info(f"Phishing Simulation Platform starting up - Log level: {logging.getLevelName(log_level)}")

    return {
        'security': security_logger,
        'email': email_logger,
        'campaign': campaign_logger
    }

def log_security_event(event_type, details, user_id=None, ip_address=None):
    """Log security events to the security log"""
    security_logger = logging.getLogger('security')

    event_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'details': details,
        'user_id': user_id,
        'ip_address': ip_address
    }

    security_logger.info(f"SECURITY_EVENT: {event_type} - {details} - User: {user_id} - IP: {ip_address}")

def log_email_event(event_type, campaign_id, target_email, details=None, success=True):
    """Log email sending events"""
    email_logger = logging.getLogger('email')

    log_level = logging.INFO if success else logging.ERROR

    event_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'campaign_id': campaign_id,
        'target_email': target_email,
        'details': details,
        'success': success
    }

    email_logger.log(log_level, f"EMAIL_EVENT: {event_type} - Campaign {campaign_id} - {target_email} - {details}")

def log_campaign_event(event_type, campaign_id, details=None, user_id=None):
    """Log campaign management events"""
    campaign_logger = logging.getLogger('campaign')

    event_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'campaign_id': campaign_id,
        'details': details,
        'user_id': user_id
    }

    campaign_logger.info(f"CAMPAIGN_EVENT: {event_type} - Campaign {campaign_id} - {details} - User: {user_id}")

def handle_application_error(app, error, context=None):
    """Handle and log application errors"""
    error_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')

    error_data = {
        'error_id': error_id,
        'timestamp': datetime.utcnow().isoformat(),
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'user_agent': getattr(request, 'user_agent', None) if 'request' in globals() else None,
        'remote_addr': getattr(request, 'remote_addr', None) if 'request' in globals() else None,
        'url': getattr(request, 'url', None) if 'request' in globals() else None
    }

    # Log to application error log
    app.logger.error(f"APPLICATION_ERROR [{error_id}]: {error_data['error_type']} - {error_data['error_message']} - Context: {context}")

    # Log security-relevant errors separately
    if is_security_relevant_error(error):
        log_security_event('APPLICATION_ERROR', error_data)

    return error_id

def is_security_relevant_error(error):
    """Determine if an error might have security implications"""
    security_error_indicators = [
        'unauthorized', 'forbidden', 'authentication', 'permission',
        'csrf', 'injection', 'xss', 'security', 'validation',
        'access denied', 'token', 'credential'
    ]

    error_message = str(error).lower()
    error_type = type(error).__name__.lower()

    combined_text = f"{error_message} {error_type}"

    return any(indicator in combined_text for indicator in security_error_indicators)

class ContextualLogger:
    """Logger that adds context to log messages"""

    def __init__(self, base_logger, context=None):
        self.logger = base_logger
        self.context = context or {}

    def _format_message(self, message):
        """Format message with context"""
        if self.context:
            context_str = ' - '.join([f"{k}: {v}" for k, v in self.context.items()])
            return f"{message} | {context_str}"
        return message

    def debug(self, message, **kwargs):
        self.logger.debug(self._format_message(message), **kwargs)

    def info(self, message, **kwargs):
        self.logger.info(self._format_message(message), **kwargs)

    def warning(self, message, **kwargs):
        self.logger.warning(self._format_message(message), **kwargs)

    def error(self, message, **kwargs):
        self.logger.error(self._format_message(message), **kwargs)

    def critical(self, message, **kwargs):
        self.logger.critical(self._format_message(message), **kwargs)

    def add_context(self, **kwargs):
        """Add context to future log messages"""
        self.context.update(kwargs)
        return self

    def set_context(self, **kwargs):
        """Set context (replaces existing context)"""
        self.context = kwargs
        return self

def get_contextual_logger(name, context=None):
    """Get a logger with contextual information"""
    base_logger = logging.getLogger(name)
    return ContextualLogger(base_logger, context)