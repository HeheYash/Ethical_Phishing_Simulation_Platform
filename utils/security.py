import bleach
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort
from flask_login import current_user
import re
from datetime import datetime, timezone
import hashlib

def sanitize_html(content):
    """Sanitize HTML content to prevent XSS attacks"""
    allowed_tags = [
        'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol',
        'strong', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'div', 'span',
        'table', 'tr', 'td', 'th', 'thead', 'tbody', 'style'
    ]
    allowed_attributes = {
        'a': ['href', 'title', 'target'],
        'abbr': ['title'],
        'acronym': ['title'],
        'div': ['class', 'style'],
        'span': ['class', 'style'],
        'p': ['class', 'style'],
        'table': ['class', 'style'],
        'tr': ['class', 'style'],
        'td': ['class', 'style', 'colspan'],
        'th': ['class', 'style', 'colspan'],
        'h1': ['class', 'style'],
        'h2': ['class', 'style'],
        'h3': ['class', 'style'],
        'h4': ['class', 'style'],
        'h5': ['class', 'style'],
        'h6': ['class', 'style']
    }
    allowed_styles = [
        'color', 'background-color', 'font-size', 'font-family', 'font-weight',
        'text-align', 'text-decoration', 'margin', 'padding', 'border', 'width'
    ]

    return bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        styles=allowed_styles,
        strip=True
    )

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def generate_token():
    """Generate a secure random token"""
    import secrets
    return secrets.token_urlsafe(32)

def hash_data(data):
    """Hash sensitive data (for storing hashes without storing the actual data)"""
    return hashlib.sha256(data.encode()).hexdigest()

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def log_audit(action, resource_type=None, resource_id=None, details=None):
    """Log audit trail for security compliance"""
    from database.models import AuditLog
    from flask_login import current_user
    from app import db
    import json

    audit_log = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=json.dumps(details) if details else None,
        ip_address=request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    )

    db.session.add(audit_log)
    db.session.commit()

def verify_consent_required():
    """Check if campaign consent is required and properly verified"""
    from flask import current_app
    return current_app.config.get('CAMPAIGN_CONSENT_REQUIRED', True)

def sanitize_filename(filename):
    """Sanitize filename to prevent directory traversal"""
    # Remove directory separators
    filename = filename.replace('/', '').replace('..', '')
    # Remove dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Limit length
    filename = filename[:100]
    return filename

def is_safe_url(target):
    """Check if URL is safe for redirects"""
    from urllib.parse import urlparse
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)

    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

def rate_limit_check(identifier, limit, window=60):
    """Simple rate limiting implementation"""
    from flask import current_app
    import time

    # Use Redis if available, otherwise use in-memory store
    try:
        import redis
        r = redis.from_url(current_app.config.get('REDIS_URL', 'redis://localhost:6379/0'))
        key = f"rate_limit:{identifier}"
        current = r.get(key)
        if current and int(current) >= limit:
            return False
        if current:
            r.incr(key)
        else:
            r.set(key, 1, ex=window)
        return True
    except:
        # Fallback to simple in-memory check (not ideal for production)
        return True

def validate_template_variables(content):
    """Validate that template variables are properly formatted"""
    import re
    # Find all template variables in content
    variables = re.findall(r'\{\{(\w+)\}\}', content)
    # Allow only safe variables
    allowed_variables = [
        'first_name', 'last_name', 'email', 'department', 'company',
        'click_url', 'tracking_pixel', 'tracking_number', 'campaign_name',
        'sender_name', 'sender_email'
    ]

    for var in variables:
        if var not in allowed_variables:
            raise ValueError(f"Template variable '{var}' is not allowed")

    return True

def mask_email(email):
    """Mask email for display (e.g., j***@example.com)"""
    if '@' not in email:
        return email

    local, domain = email.split('@', 1)
    if len(local) <= 1:
        return f"{local}@{domain}"

    masked_local = local[0] + '*' * (len(local) - 2) + local[-1] if len(local) > 2 else local[0] + '*'
    return f"{masked_local}@{domain}"