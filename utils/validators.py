from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, FileField, IntegerField, DateTimeField, EmailField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from database.models import User, Campaign, Template
import re

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

class CampaignForm(FlaskForm):
    name = StringField('Campaign Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    template_id = SelectField('Email Template', coerce=int, validators=[DataRequired()])
    consent_verified = BooleanField('I have obtained proper consent from all targets', validators=[DataRequired()])
    scheduled_at = DateTimeField('Schedule (Optional)', validators=[Optional()], format='%Y-%m-%d %H:%M')
    submit = SubmitField('Create Campaign')

    def __init__(self, *args, **kwargs):
        super(CampaignForm, self).__init__(*args, **kwargs)
        self.template_id.choices = [(t.id, t.name) for t in Template.query.filter_by(is_active=True).all()]

class TemplateForm(FlaskForm):
    name = StringField('Template Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    subject = StringField('Email Subject', validators=[DataRequired(), Length(max=200)])
    html_content = TextAreaField('HTML Content', validators=[DataRequired()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Template')

    def validate_html_content(self, html_content):
        # Basic template validation
        if not html_content.data.strip():
            raise ValidationError('HTML content cannot be empty.')

        # Check for template variables
        import re
        variables = re.findall(r'\{\{(\w+)\}\}', html_content.data)
        allowed_variables = [
            'first_name', 'last_name', 'email', 'department', 'company',
            'click_url', 'tracking_pixel', 'tracking_number', 'campaign_name',
            'sender_name', 'sender_email'
        ]

        for var in variables:
            if var not in allowed_variables:
                raise ValidationError(f"Template variable '{var}' is not allowed. Allowed variables: {', '.join(allowed_variables)}")

class TargetImportForm(FlaskForm):
    csv_file = FileField('CSV File', validators=[DataRequired()])
    submit = SubmitField('Import Targets')

class TargetForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[Optional(), Length(max=100)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=100)])
    department = StringField('Department', validators=[Optional(), Length(max=100)])
    submit = SubmitField('Add Target')

    def validate_email(self, email):
        from database.models import Target
        target = Target.query.filter_by(email=email.data).first()
        if target:
            raise ValidationError('Email already exists in target list.')

class SettingsForm(FlaskForm):
    campaign_consent_required = BooleanField('Require consent verification for campaigns')
    data_retention_days = IntegerField('Data Retention Days', validators=[DataRequired(), NumberRange(min=1, max=365)])
    max_emails_per_hour = IntegerField('Max Emails Per Hour', validators=[DataRequired(), NumberRange(min=1, max=1000)])
    submit = SubmitField('Save Settings')

def validate_csv_file(file):
    """Validate CSV file format and content"""
    if not file.filename.endswith('.csv'):
        raise ValidationError('File must be a CSV file.')

    if file.content_length > 10 * 1024 * 1024:  # 10MB limit
        raise ValidationError('File too large. Maximum size is 10MB.')

    # Read and validate CSV structure
    content = file.read().decode('utf-8')
    file.seek(0)

    lines = content.split('\n')
    if len(lines) < 2:
        raise ValidationError('CSV file must contain at least a header and one data row.')

    # Check required headers
    headers = [h.strip().lower() for h in lines[0].split(',')]
    if 'email' not in headers:
        raise ValidationError('CSV must have an "email" column.')

def validate_campaign_name(name):
    """Validate campaign name for uniqueness and format"""
    if not name or len(name.strip()) < 3:
        raise ValidationError('Campaign name must be at least 3 characters long.')

    if len(name) > 100:
        raise ValidationError('Campaign name must be less than 100 characters.')

    # Check for unique name
    existing = Campaign.query.filter_by(name=name.strip()).first()
    if existing:
        raise ValidationError('Campaign name already exists.')

def validate_email_list(email_list):
    """Validate a list of email addresses"""
    if not email_list or not email_list.strip():
        raise ValidationError('Email list cannot be empty.')

    emails = [email.strip() for email in email_list.split(',') if email.strip()]
    if not emails:
        raise ValidationError('No valid email addresses found.')

    invalid_emails = []
    for email in emails:
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            invalid_emails.append(email)

    if invalid_emails:
        raise ValidationError(f'Invalid email addresses: {", ".join(invalid_emails)}')

    return emails