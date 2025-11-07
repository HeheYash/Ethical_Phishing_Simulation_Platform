from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from database.models import Campaign, CampaignTarget, EmailEvent, Target, Template
from utils.helpers import calculate_campaign_metrics, format_number, format_percentage, get_campaign_timeline_data
from utils.security import admin_required
from sqlalchemy import func, desc
from datetime import datetime, timezone, timedelta
from app import db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard with overview statistics"""
    # Get basic counts
    total_campaigns = Campaign.query.count()
    active_campaigns = Campaign.query.filter_by(status='active').count()
    total_targets = Target.query.count()
    total_templates = Template.query.filter_by(is_active=True).count()

    # Get recent campaigns
    recent_campaigns = Campaign.query.order_by(desc(Campaign.created_at)).limit(5).all()

    # Get campaign metrics for recent campaigns
    campaign_metrics = {}
    for campaign in recent_campaigns:
        campaign_metrics[campaign.id] = calculate_campaign_metrics(campaign.id)

    # Get overall statistics
    overall_metrics = get_overall_statistics()

    return render_template('dashboard/index.html',
                         total_campaigns=total_campaigns,
                         active_campaigns=active_campaigns,
                         total_targets=total_targets,
                         total_templates=total_templates,
                         recent_campaigns=recent_campaigns,
                         campaign_metrics=campaign_metrics,
                         overall_metrics=overall_metrics)

@dashboard_bp.route('/api/chart_data')
@login_required
def chart_data():
    """API endpoint for dashboard chart data"""
    chart_type = request.args.get('type', 'campaign_timeline')
    time_range = request.args.get('range', '7d')  # 7d, 30d, 90d

    if chart_type == 'campaign_timeline':
        data = get_campaign_timeline_data(time_range)
    elif chart_type == 'activity_summary':
        data = get_activity_summary_data(time_range)
    elif chart_type == 'department_performance':
        data = get_department_performance_data()
    else:
        data = {'error': 'Invalid chart type'}

    return jsonify(data)

@dashboard_bp.route('/campaigns')
@login_required
def campaigns():
    """Campaigns overview page"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')

    query = Campaign.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    campaigns = query.order_by(desc(Campaign.created_at)).paginate(
        page=page, per_page=20, error_out=False)

    # Get metrics for each campaign
    campaign_metrics = {}
    for campaign in campaigns.items:
        campaign_metrics[campaign.id] = calculate_campaign_metrics(campaign.id)

    return render_template('dashboard/campaigns.html',
                         campaigns=campaigns,
                         campaign_metrics=campaign_metrics,
                         status_filter=status_filter)

@dashboard_bp.route('/targets')
@login_required
def targets():
    """Targets management page"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = Target.query

    if search:
        query = query.filter(
            (Target.email.contains(search)) |
            (Target.first_name.contains(search)) |
            (Target.last_name.contains(search)) |
            (Target.department.contains(search))
        )

    targets = query.filter_by(is_active=True).order_by(
        Target.email).paginate(page=page, per_page=50, error_out=False)

    return render_template('dashboard/targets.html', targets=targets, search=search)

@dashboard_bp.route('/templates')
@login_required
def templates():
    """Templates management page"""
    templates = Template.query.order_by(desc(Template.created_at)).all()

    # Get usage statistics for each template
    template_stats = {}
    for template in templates:
        usage_count = Campaign.query.filter_by(template_id=template.id).count()
        recent_usage = Campaign.query.filter_by(template_id=template.id).filter(
            Campaign.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
        ).count()

        template_stats[template.id] = {
            'total_usage': usage_count,
            'recent_usage': recent_usage
        }

    return render_template('dashboard/templates.html',
                         templates=templates,
                         template_stats=template_stats)

@dashboard_bp.route('/settings')
@login_required
@admin_required
def settings():
    """Application settings page (admin only)"""
    from flask import current_app

    settings_data = {
        'campaign_consent_required': current_app.config.get('CAMPAIGN_CONSENT_REQUIRED', True),
        'data_retention_days': current_app.config.get('DATA_RETENTION_DAYS', 90),
        'max_emails_per_hour': current_app.config.get('MAX_EMAILS_PER_HOUR', 100),
        'rate_limit_per_minute': current_app.config.get('RATE_LIMIT_PER_MINUTE', 60),
        'session_timeout': current_app.config.get('SESSION_TIMEOUT', 3600)
    }

    return render_template('dashboard/settings.html', settings=settings_data)

@dashboard_bp.route('/help')
@login_required
def help():
    """Help and documentation page"""
    return render_template('dashboard/help.html')

def get_overall_statistics():
    """Get overall platform statistics"""
    total_events = EmailEvent.query.count()
    total_opens = EmailEvent.query.filter_by(event_type='opened').distinct(EmailEvent.campaign_target_id).count()
    total_clicks = EmailEvent.query.filter_by(event_type='clicked').distinct(EmailEvent.campaign_target_id).count()
    total_submissions = EmailEvent.query.filter_by(event_type='submitted').distinct(EmailEvent.campaign_target_id).count()

    # Get campaign counts by status
    campaign_stats = db.session.query(
        Campaign.status,
        func.count(Campaign.id).label('count')
    ).group_by(Campaign.status).all()

    status_counts = {status: 0 for status in ['draft', 'active', 'completed', 'paused']}
    for status, count in campaign_stats:
        status_counts[status] = count

    return {
        'total_events': format_number(total_events),
        'unique_opens': format_number(total_opens),
        'unique_clicks': format_number(total_clicks),
        'unique_submissions': format_number(total_submissions),
        'campaign_status_counts': status_counts
    }

def get_campaign_timeline_data(time_range):
    """Get campaign activity timeline data"""
    # Determine date range
    days = {'7d': 7, '30d': 30, '90d': 90}.get(time_range, 7)
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Get daily event counts
    events_by_day = db.session.query(
        func.date(EmailEvent.timestamp).label('date'),
        EmailEvent.event_type,
        func.count(EmailEvent.id).label('count')
    ).filter(
        EmailEvent.timestamp >= start_date
    ).group_by(
        func.date(EmailEvent.timestamp),
        EmailEvent.event_type
    ).all()

    # Convert to chart format
    data_dict = {}
    for event in events_by_day:
        date_str = event.date.strftime('%Y-%m-%d')
        if date_str not in data_dict:
            data_dict[date_str] = {'sent': 0, 'opened': 0, 'clicked': 0, 'submitted': 0}
        data_dict[date_str][event.event_type] = event.count

    # Fill missing dates with zeros
    timeline_data = []
    for i in range(days):
        date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime('%Y-%m-%d')
        timeline_data.append({
            'date': date,
            'sent': data_dict.get(date, {}).get('sent', 0),
            'opened': data_dict.get(date, {}).get('opened', 0),
            'clicked': data_dict.get(date, {}).get('clicked', 0),
            'submitted': data_dict.get(date, {}).get('submitted', 0)
        })

    return {'timeline': timeline_data[::-1]}  # Reverse to get oldest first

def get_activity_summary_data(time_range):
    """Get activity summary for pie charts"""
    days = {'7d': 7, '30d': 30, '90d': 90}.get(time_range, 7)
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Event type counts
    event_counts = db.session.query(
        EmailEvent.event_type,
        func.count(EmailEvent.id).label('count')
    ).filter(
        EmailEvent.timestamp >= start_date
    ).group_by(EmailEvent.event_type).all()

    # Campaign status counts
    campaign_counts = db.session.query(
        Campaign.status,
        func.count(Campaign.id).label('count')
    ).filter(
        Campaign.created_at >= start_date
    ).group_by(Campaign.status).all()

    return {
        'events': [{'name': event.event_type, 'value': event.count} for event in event_counts],
        'campaigns': [{'name': status, 'value': count} for status, count in campaign_counts]
    }

def get_department_performance_data():
    """Get performance data by department"""
    department_stats = db.session.query(
        Target.department,
        func.count(Target.id).label('target_count'),
        func.count(func.distinct(EmailEvent.campaign_target_id)).label('interacted_count')
    ).join(
        CampaignTarget, Target.id == CampaignTarget.target_id
    ).join(
        EmailEvent, CampaignTarget.id == EmailEvent.campaign_target_id
    ).filter(
        EmailEvent.event_type.in_(['opened', 'clicked', 'submitted']),
        Target.department.isnot(None)
    ).group_by(Target.department).all()

    department_data = []
    for dept in department_stats:
        if dept.department:  # Exclude None departments
            interaction_rate = (dept.interacted_count / dept.target_count * 100) if dept.target_count > 0 else 0
            department_data.append({
                'department': dept.department,
                'target_count': dept.target_count,
                'interacted_count': dept.interacted_count,
                'interaction_rate': round(interaction_rate, 2)
            })

    return {'departments': department_data}