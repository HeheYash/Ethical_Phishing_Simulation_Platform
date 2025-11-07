from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
import uuid
import json

class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Template(db.Model):
    """Email template model for phishing campaigns"""
    __tablename__ = 'templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    subject = db.Column(db.String(200), nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship
    creator = db.relationship('User', backref='templates')

    def __repr__(self):
        return f'<Template {self.name}>'

class Campaign(db.Model):
    """Campaign model for phishing simulations"""
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'), nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, active, completed, paused
    consent_verified = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    scheduled_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Relationships
    template = db.relationship('Template', backref='campaigns')
    creator = db.relationship('User', backref='campaigns')

    def __repr__(self):
        return f'<Campaign {self.name}>'

class Target(db.Model):
    """Target model for phishing campaign recipients"""
    __tablename__ = 'targets'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def __repr__(self):
        return f'<Target {self.email}>'

class CampaignTarget(db.Model):
    """Many-to-many relationship between campaigns and targets"""
    __tablename__ = 'campaign_targets'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('targets.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, sent, opened, clicked, submitted
    unique_token = db.Column(db.String(64), unique=True, nullable=False)
    consent_given = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    sent_at = db.Column(db.DateTime)

    # Relationships
    campaign = db.relationship('Campaign', backref='campaign_targets')
    target = db.relationship('Target', backref='campaign_targets')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.unique_token:
            self.unique_token = uuid.uuid4().hex

    def __repr__(self):
        return f'<CampaignTarget {self.campaign_id}-{self.target_id}>'

class EmailEvent(db.Model):
    """Event tracking model for email interactions"""
    __tablename__ = 'email_events'

    id = db.Column(db.Integer, primary_key=True)
    campaign_target_id = db.Column(db.Integer, db.ForeignKey('campaign_targets.id'), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)  # sent, opened, clicked, submitted, bounced
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.Text)
    metadata = db.Column(db.Text)  # JSON string for additional context

    # Relationship
    campaign_target = db.relationship('CampaignTarget', backref='events')

    def set_metadata(self, data):
        self.metadata = json.dumps(data) if data else None

    def get_metadata(self):
        return json.loads(self.metadata) if self.metadata else {}

    def __repr__(self):
        return f'<EmailEvent {self.event_type} for {self.campaign_target_id}>'

class AuditLog(db.Model):
    """Audit log for security and compliance"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50))  # campaign, template, target, etc.
    resource_id = db.Column(db.Integer)
    details = db.Column(db.Text)  # JSON string of changes
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship
    user = db.relationship('User', backref='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_id}>'

# Helper function to create sample data
def create_sample_data():
    """Create sample data for testing and demonstration"""
    from app import app

    with app.app_context():
        # Create admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)

        # Create sample templates
        if not Template.query.first():
            template1 = Template(
                name='IT Support Alert',
                description='Urgent IT account verification required',
                subject='URGENT: Immediate Action Required - Account Verification',
                html_content='''
                <html>
                <body>
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #d32f2f;">⚠️ Security Alert</h2>
                        <p>Dear {{first_name}},</p>
                        <p>We have detected unusual activity on your account. Your immediate attention is required.</p>
                        <p style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107;">
                            <strong>Alert Details:</strong><br>
                            - Multiple login attempts detected<br>
                            - Suspicious IP address identified<br>
                            - Account access temporarily restricted
                        </p>
                        <p>Please click the link below to verify your identity and restore access:</p>
                        <p>
                            <a href="{{click_url}}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                                Verify Account Now
                            </a>
                        </p>
                        <p><small>This link will expire in 24 hours.</small></p>
                        <p>IT Security Team<br>
                        <small>This is a simulated security test. {{tracking_pixel}}</small></p>
                    </div>
                </body>
                </html>
                ''',
                created_by=1
            )
            template2 = Template(
                name='Package Delivery Notification',
                description='Fake delivery notification with tracking link',
                subject='Package Delivery Alert: Action Required',
                html_content='''
                <html>
                <body>
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2>📦 Package Delivery</h2>
                        <p>Hello {{first_name}},</p>
                        <p>We attempted to deliver your package but were unable to complete the delivery.</p>
                        <div style="background-color: #e3f2fd; padding: 15px; border-left: 4px solid #2196f3;">
                            <strong>Delivery Information:</strong><br>
                            - Tracking Number: PKG-{{tracking_number}}<br>
                            - Delivery Date: Today<br>
                            - Status: Action Required
                        </div>
                        <p>Please click the link below to confirm your delivery details:</p>
                        <p>
                            <a href="{{click_url}}" style="background-color: #4caf50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                                Confirm Delivery Details
                            </a>
                        </p>
                        <p><strong>Note:</strong> Package will be returned to sender if not confirmed within 48 hours.</p>
                        <p>Delivery Services<br>
                        <small>Security simulation test - {{tracking_pixel}}</small></p>
                    </div>
                </body>
                </html>
                ''',
                created_by=1
            )
            db.session.add(template1)
            db.session.add(template2)

        # Create sample targets
        if not Target.query.first():
            targets = [
                Target(email='john.doe@example.com', first_name='John', last_name='Doe', department='IT'),
                Target(email='jane.smith@example.com', first_name='Jane', last_name='Smith', department='HR'),
                Target(email='bob.wilson@example.com', first_name='Bob', last_name='Wilson', department='Finance'),
                Target(email='alice.brown@example.com', first_name='Alice', last_name='Brown', department='Marketing'),
                Target(email='charlie.davis@example.com', first_name='Charlie', last_name='Davis', department='Operations')
            ]
            for target in targets:
                db.session.add(target)

        db.session.commit()
        print("Sample data created successfully!")