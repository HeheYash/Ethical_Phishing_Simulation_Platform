from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from flask_login import login_required, current_user
from database.models import Campaign, CampaignTarget, EmailEvent, Target, Template
from utils.helpers import calculate_campaign_metrics, generate_csv_export, format_number, format_percentage, get_campaign_timeline_data
from utils.security import admin_required, log_audit
from sqlalchemy import func, desc, and_, or_
from datetime import datetime, timezone, timedelta
from app import db
import io
import csv

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/')
@login_required
def dashboard():
    """Main analytics dashboard"""
    # Get campaign list for filtering
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()

    # Non-admin users can only see their own campaigns
    if not current_user.is_admin:
        campaigns = [c for c in campaigns if c.created_by == current_user.id]

    return render_template('analytics/dashboard.html', campaigns=campaigns)

@analytics_bp.route('/campaign/<int:id>')
@login_required
def campaign_analytics(id):
    """Detailed analytics for a specific campaign"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('analytics.dashboard'))

    # Get campaign metrics
    metrics = calculate_campaign_metrics(id)

    # Get timeline data
    timeline_data = get_campaign_timeline_data(id)

    # Get target details with status
    targets_query = db.session.query(
        CampaignTarget,
        Target,
        EmailEvent
    ).outerjoin(
        Target, CampaignTarget.target_id == Target.id
    ).outerjoin(
        EmailEvent, CampaignTarget.id == EmailEvent.campaign_target_id
    ).filter(
        CampaignTarget.campaign_id == id
    ).all()

    # Process targets data
    targets_data = []
    for campaign_target, target, event in targets_query:
        target_info = {
            'id': target.id,
            'email': target.email,
            'first_name': target.first_name,
            'last_name': target.last_name,
            'department': target.department,
            'status': campaign_target.status,
            'sent_time': None,
            'open_time': None,
            'click_time': None,
            'submit_time': None,
            'time_to_open': None,
            'time_to_click': None
        }

        # Get events for this target
        events = EmailEvent.query.filter_by(campaign_target_id=campaign_target.id).order_by(EmailEvent.timestamp).all()

        for event in events:
            if event.event_type == 'sent':
                target_info['sent_time'] = event.timestamp
            elif event.event_type == 'opened':
                target_info['open_time'] = event.timestamp
                if target_info['sent_time']:
                    target_info['time_to_open'] = (event.timestamp - target_info['sent_time']).total_seconds() / 60  # minutes
            elif event.event_type == 'clicked':
                target_info['click_time'] = event.timestamp
                if target_info['sent_time']:
                    target_info['time_to_click'] = (event.timestamp - target_info['sent_time']).total_seconds() / 60  # minutes
            elif event.event_type == 'submitted':
                target_info['submit_time'] = event.timestamp

        targets_data.append(target_info)

    # Department breakdown
    department_stats = db.session.query(
        Target.department,
        func.count(Target.id).label('total_targets'),
        func.count(func.distinct(EmailEvent.campaign_target_id)).label('engaged_targets')
    ).join(
        CampaignTarget, Target.id == CampaignTarget.target_id
    ).join(
        EmailEvent, CampaignTarget.id == EmailEvent.campaign_target_id
    ).filter(
        CampaignTarget.campaign_id == id,
        EmailEvent.event_type.in_(['opened', 'clicked', 'submitted']),
        Target.department.isnot(None)
    ).group_by(Target.department).all()

    return render_template('analytics/campaign_detail.html',
                         campaign=campaign,
                         metrics=metrics,
                         timeline_data=timeline_data,
                         targets_data=targets_data,
                         department_stats=department_stats)

@analytics_bp.route('/export/campaign/<int:id>')
@login_required
def export_campaign(id):
    """Export campaign data as CSV"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('analytics.dashboard'))

    try:
        csv_content = generate_csv_export(id)

        # Create response
        output = io.BytesIO()
        output.write(csv_content.encode('utf-8'))
        output.seek(0)

        filename = f"campaign_{id}_{campaign.name}_{datetime.now().strftime('%Y%m%d')}.csv"

        log_audit('CAMPAIGN_EXPORTED', 'campaign', campaign.id, {'format': 'csv'})

        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.error(f"Export error for campaign {id}: {str(e)}")
        flash('An error occurred while exporting the campaign data.', 'danger')
        return redirect(url_for('analytics.campaign_analytics', id=id))

@analytics_bp.route('/overview')
@login_required
def overview():
    """Platform-wide analytics overview (admin only)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('analytics.dashboard'))

    # Get overall statistics
    total_campaigns = Campaign.query.count()
    total_targets = Target.query.count()
    total_events = EmailEvent.query.count()

    # Campaign status breakdown
    campaign_status = db.session.query(
        Campaign.status,
        func.count(Campaign.id).label('count')
    ).group_by(Campaign.status).all()

    # Event type breakdown
    event_types = db.session.query(
        EmailEvent.event_type,
        func.count(EmailEvent.id).label('count')
    ).group_by(EmailEvent.event_type).all()

    # Recent activity
    recent_campaigns = Campaign.query.order_by(desc(Campaign.created_at)).limit(10).all()
    recent_events = EmailEvent.query.order_by(desc(EmailEvent.timestamp)).limit(20).all()

    # Performance metrics
    active_campaigns = Campaign.query.filter_by(status='active').all()
    campaign_performances = []

    for campaign in active_campaigns:
        metrics = calculate_campaign_metrics(campaign.id)
        campaign_performances.append({
            'campaign': campaign,
            'metrics': metrics
        })

    return render_template('analytics/overview.html',
                         total_campaigns=total_campaigns,
                         total_targets=total_targets,
                         total_events=total_events,
                         campaign_status=campaign_status,
                         event_types=event_types,
                         recent_campaigns=recent_campaigns,
                         recent_events=recent_events,
                         campaign_performances=campaign_performances)

@analytics_bp.route('/api/data')
@login_required
def api_data():
    """API endpoint for analytics data"""
    data_type = request.args.get('type', 'overview')
    campaign_id = request.args.get('campaign_id', type=int)

    try:
        if data_type == 'campaign_metrics' and campaign_id:
            data = calculate_campaign_metrics(campaign_id)
        elif data_type == 'campaign_timeline' and campaign_id:
            data = get_campaign_timeline_data(campaign_id)
        elif data_type == 'platform_overview':
            data = get_platform_overview_data()
        elif data_type == 'department_performance':
            data = get_department_performance_data(campaign_id)
        elif data_type == 'time_to_engagement':
            data = get_time_to_engagement_data(campaign_id)
        else:
            data = {'error': 'Invalid data type'}

        return jsonify(data)

    except Exception as e:
        current_app.logger.error(f"Analytics API error: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching data'}), 500

@analytics_bp.route('/reports')
@login_required
def reports():
    """Reports page"""
    return render_template('analytics/reports.html')

@analytics_bp.route('/reports/compliance')
@login_required
@admin_required
def compliance_report():
    """Compliance and audit report"""
    # Get audit logs for the last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    audit_logs = db.session.query(
        AuditLog
    ).filter(
        AuditLog.timestamp >= thirty_days_ago
    ).order_by(
        desc(AuditLog.timestamp)
    ).limit(100).all()

    # Get campaign consent verification status
    consent_compliance = db.session.query(
        Campaign.consent_verified,
        func.count(Campaign.id).label('count')
    ).filter(
        Campaign.created_at >= thirty_days_ago
    ).group_by(Campaign.consent_verified).all()

    # Data retention analysis
    old_events = EmailEvent.query.filter(
        EmailEvent.timestamp < datetime.now(timezone.utc) - timedelta(days=current_app.config.get('DATA_RETENTION_DAYS', 90))
    ).count()

    return render_template('analytics/compliance_report.html',
                         audit_logs=audit_logs,
                         consent_compliance=consent_compliance,
                         old_events=old_events)

def get_platform_overview_data():
    """Get platform-wide overview data for charts"""
    # Last 30 days activity
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Daily event counts
    daily_events = db.session.query(
        func.date(EmailEvent.timestamp).label('date'),
        EmailEvent.event_type,
        func.count(EmailEvent.id).label('count')
    ).filter(
        EmailEvent.timestamp >= thirty_days_ago
    ).group_by(
        func.date(EmailEvent.timestamp),
        EmailEvent.event_type
    ).all()

    # Campaign creation trends
    campaign_trends = db.session.query(
        func.date(Campaign.created_at).label('date'),
        func.count(Campaign.id).label('count')
    ).filter(
        Campaign.created_at >= thirty_days_ago
    ).group_by(
        func.date(Campaign.created_at)
    ).all()

    # Convert to chart format
    events_data = {}
    for event in daily_events:
        date_str = event.date.strftime('%Y-%m-%d')
        if date_str not in events_data:
            events_data[date_str] = {'opened': 0, 'clicked': 0, 'submitted': 0}
        events_data[date_str][event.event_type] = event.count

    campaigns_data = {}
    for campaign in campaign_trends:
        campaigns_data[campaign.date.strftime('%Y-%m-%d')] = campaign.count

    return {
        'daily_events': events_data,
        'campaign_trends': campaigns_data
    }

def get_department_performance_data(campaign_id=None):
    """Get performance data by department"""
    query = db.session.query(
        Target.department,
        func.count(Target.id).label('total_targets'),
        func.count(func.distinct(EmailEvent.campaign_target_id)).label('engaged_targets'),
        func.count(func.distinct(CampaignTarget.id)).label('campaign_targets')
    ).join(
        CampaignTarget, Target.id == CampaignTarget.target_id
    ).outerjoin(
        EmailEvent, CampaignTarget.id == EmailEvent.campaign_target_id
    ).filter(
        Target.department.isnot(None)
    )

    if campaign_id:
        query = query.filter(CampaignTarget.campaign_id == campaign_id)

    department_stats = query.group_by(Target.department).all()

    department_data = []
    for dept in department_stats:
        if dept.department:  # Exclude None departments
            engagement_rate = (dept.engaged_targets / dept.campaign_targets * 100) if dept.campaign_targets > 0 else 0
            department_data.append({
                'department': dept.department,
                'total_targets': dept.total_targets,
                'campaign_targets': dept.campaign_targets,
                'engaged_targets': dept.engaged_targets,
                'engagement_rate': round(engagement_rate, 2)
            })

    return {'departments': department_data}

def get_time_to_engagement_data(campaign_id):
    """Get time-to-engagement metrics"""
    # Average time to open and click
    time_data = db.session.query(
        Target.email,
        EmailEvent.event_type,
        EmailEvent.timestamp,
        func.lag(EmailEvent.timestamp).over(
            partition_by=EmailEvent.campaign_target_id,
            order_by=EmailEvent.timestamp
        ).label('prev_timestamp')
    ).join(
        CampaignTarget, EmailEvent.campaign_target_id == CampaignTarget.id
    ).join(
        Target, CampaignTarget.target_id == Target.id
    ).filter(
        CampaignTarget.campaign_id == campaign_id,
        EmailEvent.event_type.in_(['opened', 'clicked'])
    ).subquery()

    # Process the data to calculate time differences
    # This is a simplified version - in production you'd want more sophisticated time analysis

    return {
        'avg_time_to_open': 15.5,  # Placeholder - would calculate from actual data
        'avg_time_to_click': 45.2,  # Placeholder - would calculate from actual data
        'quartiles': {
            'q1_open': 5.0,
            'median_open': 12.0,
            'q3_open': 25.0,
            'q1_click': 20.0,
            'median_click': 40.0,
            'q3_click': 60.0
        }
    }