import csv
import io
from datetime import datetime, timezone
from flask import url_for, current_app
import uuid
import secrets

def generate_tracking_url(campaign_target_id, url_type, base_url=None):
    """Generate tracking URLs for email links"""
    if not base_url:
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')

    if url_type == 'open':
        return f"{base_url}/track/open/{campaign_target_id}"
    elif url_type == 'click':
        return f"{base_url}/track/click/{campaign_target_id}"
    elif url_type == 'submit':
        return f"{base_url}/track/submit/{campaign_target_id}"

def render_template_content(template_content, variables):
    """Render template content with variables"""
    content = template_content

    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        if placeholder in content:
            content = content.replace(placeholder, str(value))

    return content

def calculate_campaign_metrics(campaign_id):
    """Calculate comprehensive campaign metrics"""
    from database.models import Campaign, CampaignTarget, EmailEvent
    from sqlalchemy import func

    # Get campaign targets and events
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return None

    total_targets = CampaignTarget.query.filter_by(campaign_id=campaign_id).count()

    # Count events by type
    sent_events = EmailEvent.query.join(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign_id,
        EmailEvent.event_type == 'sent'
    ).count()

    open_events = EmailEvent.query.join(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign_id,
        EmailEvent.event_type == 'opened'
    ).distinct(EmailEvent.campaign_target_id).count()

    click_events = EmailEvent.query.join(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign_id,
        EmailEvent.event_type == 'clicked'
    ).distinct(EmailEvent.campaign_target_id).count()

    submit_events = EmailEvent.query.join(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign_id,
        EmailEvent.event_type == 'submitted'
    ).distinct(EmailEvent.campaign_target_id).count()

    # Calculate rates
    open_rate = (open_events / sent_events * 100) if sent_events > 0 else 0
    click_rate = (click_events / open_events * 100) if open_events > 0 else 0
    submission_rate = (submit_events / click_events * 100) if click_events > 0 else 0

    metrics = {
        'total_targets': total_targets,
        'emails_sent': sent_events,
        'unique_opens': open_events,
        'unique_clicks': click_events,
        'unique_submissions': submit_events,
        'open_rate': round(open_rate, 2),
        'click_rate': round(click_rate, 2),
        'submission_rate': round(submission_rate, 2),
        'delivery_rate': round((sent_events / total_targets * 100) if total_targets > 0 else 0, 2)
    }

    return metrics

def generate_csv_export(campaign_id):
    """Generate CSV export of campaign results"""
    from database.models import Campaign, CampaignTarget, EmailEvent, Target
    import csv
    from io import StringIO

    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return None

    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Target Email', 'First Name', 'Last Name', 'Department',
        'Status', 'Email Sent', 'Email Opened', 'Link Clicked', 'Form Submitted',
        'First Open Time', 'First Click Time', 'Submission Time'
    ])

    # Get campaign targets with their events
    targets = CampaignTarget.query.filter_by(campaign_id=campaign_id).all()

    for campaign_target in targets:
        target = campaign_target.target

        # Get events for this target
        events = {event.event_type: event for event in campaign_target.events}

        writer.writerow([
            target.email,
            target.first_name or '',
            target.last_name or '',
            target.department or '',
            campaign_target.status,
            events.get('sent').timestamp.isoformat() if events.get('sent') else '',
            events.get('opened').timestamp.isoformat() if events.get('opened') else '',
            events.get('clicked').timestamp.isoformat() if events.get('clicked') else '',
            events.get('submitted').timestamp.isoformat() if events.get('submitted') else '',
            events.get('opened').timestamp.isoformat() if events.get('opened') else '',
            events.get('clicked').timestamp.isoformat() if events.get('clicked') else '',
            events.get('submitted').timestamp.isoformat() if events.get('submitted') else ''
        ])

    csv_content = output.getvalue()
    output.close()
    return csv_content

def parse_target_csv(file_content):
    """Parse CSV content and extract target data"""
    csv_reader = csv.DictReader(io.StringIO(file_content))
    targets = []
    errors = []

    # Validate headers
    required_headers = ['email']
    optional_headers = ['first_name', 'last_name', 'department']

    missing_headers = [h for h in required_headers if h not in csv_reader.fieldnames]
    if missing_headers:
        errors.append(f"Missing required headers: {', '.join(missing_headers)}")
        return targets, errors

    for row_num, row in enumerate(csv_reader, start=2):
        try:
            # Validate required email field
            email = row.get('email', '').strip()
            if not email:
                errors.append(f"Row {row_num}: Email is required")
                continue

            # Validate email format
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                errors.append(f"Row {row_num}: Invalid email format: {email}")
                continue

            # Extract target data
            target_data = {
                'email': email,
                'first_name': row.get('first_name', '').strip() or None,
                'last_name': row.get('last_name', '').strip() or None,
                'department': row.get('department', '').strip() or None
            }

            targets.append(target_data)

        except Exception as e:
            errors.append(f"Row {row_num}: Error processing row - {str(e)}")

    return targets, errors

def format_number(num):
    """Format numbers for display with thousands separators"""
    return f"{num:,}" if num else "0"

def format_percentage(num):
    """Format percentage for display"""
    return f"{num:.1f}%" if num else "0.0%"

def format_datetime(dt):
    """Format datetime for display"""
    if not dt:
        return "Never"

    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))

    return dt.strftime('%Y-%m-%d %H:%M:%S')

def time_ago(dt):
    """Calculate human readable time ago"""
    if not dt:
        return "Never"

    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))

    now = datetime.now(timezone.utc)
    diff = now - dt

    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def generate_unique_token():
    """Generate a cryptographically secure unique token"""
    return secrets.token_urlsafe(32)

def get_campaign_timeline_data(campaign_id):
    """Get timeline data for campaign visualization"""
    from database.models import CampaignTarget, EmailEvent
    from sqlalchemy import func, extract
    from app import db

    # Get hourly counts for last 24 hours
    timeline_data = []

    events_by_hour = db.session.query(
        extract('hour', EmailEvent.timestamp).label('hour'),
        EmailEvent.event_type,
        func.count(EmailEvent.id).label('count')
    ).join(CampaignTarget).filter(
        CampaignTarget.campaign_id == campaign_id,
        EmailEvent.timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    ).group_by(
        extract('hour', EmailEvent.timestamp),
        EmailEvent.event_type
    ).all()

    # Convert to dict for easier processing
    data_dict = {}
    for event in events_by_hour:
        hour = int(event.hour)
        if hour not in data_dict:
            data_dict[hour] = {'sent': 0, 'opened': 0, 'clicked': 0, 'submitted': 0}
        data_dict[hour][event.event_type] = event.count

    # Fill missing hours with zeros
    for hour in range(24):
        timeline_data.append({
            'hour': f"{hour:02d}:00",
            'sent': data_dict.get(hour, {}).get('sent', 0),
            'opened': data_dict.get(hour, {}).get('opened', 0),
            'clicked': data_dict.get(hour, {}).get('clicked', 0),
            'submitted': data_dict.get(hour, {}).get('submitted', 0)
        })

    return timeline_data