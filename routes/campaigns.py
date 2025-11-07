from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from database.models import Campaign, CampaignTarget, Target, Template, EmailEvent
from utils.validators import CampaignForm, TargetImportForm, TargetForm
from utils.security import log_audit, sanitize_html, validate_template_variables
from utils.helpers import parse_target_csv, calculate_campaign_metrics
from datetime import datetime, timezone
from sqlalchemy import func
from app import db
import csv
import io

campaigns_bp = Blueprint('campaigns', __name__)

@campaigns_bp.route('/')
@login_required
def index():
    """List all campaigns"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')

    query = Campaign.query

    # Filter by status if specified
    if status_filter:
        query = query.filter_by(status=status_filter)

    # Non-admin users can only see their own campaigns
    if not current_user.is_admin:
        query = query.filter_by(created_by=current_user.id)

    campaigns = query.order_by(Campaign.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)

    # Get metrics for each campaign
    campaign_metrics = {}
    for campaign in campaigns.items:
        campaign_metrics[campaign.id] = calculate_campaign_metrics(campaign.id)

    return render_template('campaigns/list.html',
                         campaigns=campaigns,
                         campaign_metrics=campaign_metrics,
                         status_filter=status_filter)

@campaigns_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new campaign"""
    form = CampaignForm()

    if form.validate_on_submit():
        # Validate consent requirement
        if current_app.config.get('CAMPAIGN_CONSENT_REQUIRED', True) and not form.consent_verified.data:
            flash('You must verify that consent has been obtained from all targets.', 'danger')
            return render_template('campaigns/create.html', form=form)

        campaign = Campaign(
            name=form.name.data,
            description=form.description.data,
            template_id=form.template_id.data,
            status='draft',
            consent_verified=form.consent_verified.data,
            created_by=current_user.id,
            scheduled_at=form.scheduled_at.data
        )

        db.session.add(campaign)
        db.session.commit()

        # Log campaign creation
        log_audit('CAMPAIGN_CREATED', 'campaign', campaign.id, {
            'name': campaign.name,
            'template_id': campaign.template_id
        })

        flash(f'Campaign "{campaign.name}" created successfully!', 'success')
        return redirect(url_for('campaigns.view', id=campaign.id))

    return render_template('campaigns/create.html', form=form)

@campaigns_bp.route('/<int:id>')
@login_required
def view(id):
    """View campaign details"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('campaigns.index'))

    # Get campaign targets with their status
    targets = CampaignTarget.query.filter_by(campaign_id=id).all()

    # Get campaign metrics
    metrics = calculate_campaign_metrics(id)

    # Get recent events
    recent_events = EmailEvent.query.join(CampaignTarget).filter(
        CampaignTarget.campaign_id == id
    ).order_by(EmailEvent.timestamp.desc()).limit(20).all()

    return render_template('campaigns/view.html',
                         campaign=campaign,
                         targets=targets,
                         metrics=metrics,
                         recent_events=recent_events)

@campaigns_bp.route('/<int:id>/targets', methods=['GET', 'POST'])
@login_required
def manage_targets(id):
    """Manage campaign targets"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('campaigns.index'))

    # Prevent adding targets to active campaigns
    if campaign.status == 'active':
        flash('Cannot add targets to active campaigns.', 'warning')
        return redirect(url_for('campaigns.view', id=id))

    # Forms
    import_form = TargetImportForm()
    manual_form = TargetForm()

    if import_form.validate_on_submit() and import_form.csv_file.data:
        return handle_csv_import(import_form.csv_file.data, campaign)

    if manual_form.validate_on_submit() and manual_form.submit.data:
        return handle_manual_target(manual_form, campaign)

    # Get current targets
    targets = CampaignTarget.query.filter_by(campaign_id=id).all()

    return render_template('campaigns/targets.html',
                         campaign=campaign,
                         targets=targets,
                         import_form=import_form,
                         manual_form=manual_form)

@campaigns_bp.route('/<int:id>/send', methods=['POST'])
@login_required
def send_campaign(id):
    """Send campaign emails"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('campaigns.index'))

    # Validate campaign state
    if campaign.status != 'draft':
        flash('Only draft campaigns can be sent.', 'warning')
        return redirect(url_for('campaigns.view', id=id))

    # Check if targets exist
    targets = CampaignTarget.query.filter_by(campaign_id=id).count()
    if targets == 0:
        flash('No targets assigned to this campaign.', 'warning')
        return redirect(url_for('campaigns.view', id=id))

    # Check consent verification
    if current_app.config.get('CAMPAIGN_CONSENT_REQUIRED', True) and not campaign.consent_verified:
        flash('Consent must be verified before sending campaigns.', 'danger')
        return redirect(url_for('campaigns.view', id=id))

    try:
        # Queue campaign for sending (this would typically be a background task)
        from services.email_service import queue_campaign_emails
        queue_campaign_emails(campaign)

        # Update campaign status
        campaign.status = 'active'
        campaign.started_at = datetime.now(timezone.utc)
        db.session.commit()

        # Log campaign start
        log_audit('CAMPAIGN_STARTED', 'campaign', campaign.id, {
            'target_count': targets
        })

        flash(f'Campaign "{campaign.name}" has been queued for sending to {targets} targets.', 'success')
        return redirect(url_for('campaigns.view', id=id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sending campaign {id}: {str(e)}")
        flash('An error occurred while sending the campaign. Please try again.', 'danger')
        return redirect(url_for('campaigns.view', id=id))

@campaigns_bp.route('/<int:id>/pause', methods=['POST'])
@login_required
def pause_campaign(id):
    """Pause an active campaign"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('campaigns.index'))

    if campaign.status != 'active':
        flash('Only active campaigns can be paused.', 'warning')
        return redirect(url_for('campaigns.view', id=id))

    campaign.status = 'paused'
    db.session.commit()

    log_audit('CAMPAIGN_PAUSED', 'campaign', campaign.id)
    flash('Campaign has been paused.', 'info')
    return redirect(url_for('campaigns.view', id=id))

@campaigns_bp.route('/<int:id>/complete', methods=['POST'])
@login_required
def complete_campaign(id):
    """Mark campaign as completed"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('campaigns.index'))

    if campaign.status not in ['active', 'paused']:
        flash('Only active or paused campaigns can be completed.', 'warning')
        return redirect(url_for('campaigns.view', id=id))

    campaign.status = 'completed'
    campaign.completed_at = datetime.now(timezone.utc)
    db.session.commit()

    log_audit('CAMPAIGN_COMPLETED', 'campaign', campaign.id)
    flash('Campaign has been marked as completed.', 'success')
    return redirect(url_for('campaigns.view', id=id))

@campaigns_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_campaign(id):
    """Delete a campaign"""
    campaign = Campaign.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and campaign.created_by != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('campaigns.index'))

    # Prevent deletion of active campaigns
    if campaign.status == 'active':
        flash('Cannot delete active campaigns. Pause the campaign first.', 'danger')
        return redirect(url_for('campaigns.view', id=id))

    campaign_name = campaign.name

    # Delete related records
    CampaignTarget.query.filter_by(campaign_id=id).delete()
    db.session.delete(campaign)
    db.session.commit()

    log_audit('CAMPAIGN_DELETED', 'campaign', id, {'name': campaign_name})
    flash(f'Campaign "{campaign_name}" has been deleted.', 'success')
    return redirect(url_for('campaigns.index'))

def handle_csv_import(file, campaign):
    """Handle CSV file import for campaign targets"""
    try:
        # Read CSV content
        csv_content = file.read().decode('utf-8')
        file.seek(0)

        # Parse targets
        targets, errors = parse_target_csv(csv_content)

        if errors:
            flash(f'CSV import errors: {"; ".join(errors[:5])}', 'danger')
            return redirect(url_for('campaigns.manage_targets', id=campaign.id))

        # Create targets and campaign associations
        created_count = 0
        for target_data in targets:
            # Check if target already exists
            target = Target.query.filter_by(email=target_data['email']).first()
            if not target:
                target = Target(**target_data)
                db.session.add(target)
                db.session.flush()  # Get the ID

            # Check if target is already in this campaign
            existing = CampaignTarget.query.filter_by(
                campaign_id=campaign.id,
                target_id=target.id
            ).first()

            if not existing:
                campaign_target = CampaignTarget(
                    campaign_id=campaign.id,
                    target_id=target.id,
                    status='pending'
                )
                db.session.add(campaign_target)
                created_count += 1

        db.session.commit()

        log_audit('TARGETS_IMPORTED', 'campaign', campaign.id, {
            'count': created_count,
            'source': 'csv'
        })

        flash(f'Successfully imported {created_count} targets to the campaign.', 'success')
        return redirect(url_for('campaigns.manage_targets', id=campaign.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"CSV import error: {str(e)}")
        flash('An error occurred while importing the CSV file.', 'danger')
        return redirect(url_for('campaigns.manage_targets', id=campaign.id))

def handle_manual_target(form, campaign):
    """Handle manual target addition"""
    try:
        # Check if target already exists
        target = Target.query.filter_by(email=form.email.data).first()
        if not target:
            target = Target(
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                department=form.department.data
            )
            db.session.add(target)
            db.session.flush()  # Get the ID

        # Check if target is already in this campaign
        existing = CampaignTarget.query.filter_by(
            campaign_id=campaign.id,
            target_id=target.id
        ).first()

        if existing:
            flash('Target is already assigned to this campaign.', 'warning')
        else:
            campaign_target = CampaignTarget(
                campaign_id=campaign.id,
                target_id=target.id,
                status='pending'
            )
            db.session.add(campaign_target)

            log_audit('TARGET_ADDED', 'campaign', campaign.id, {
                'target_email': target.email,
                'source': 'manual'
            })

            flash(f'Target {target.email} added to campaign.', 'success')

        db.session.commit()
        return redirect(url_for('campaigns.manage_targets', id=campaign.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Manual target addition error: {str(e)}")
        flash('An error occurred while adding the target.', 'danger')
        return redirect(url_for('campaigns.manage_targets', id=campaign.id))