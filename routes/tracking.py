from flask import Blueprint, request, redirect, url_for, abort, send_file, render_template, jsonify
from database.models import CampaignTarget, EmailEvent, Campaign
from utils.security import log_audit, rate_limit_check
from utils.helpers import time_ago
from datetime import datetime, timezone
import os
from app import db

tracking_bp = Blueprint('tracking', __name__)

@tracking_bp.route('/open/<token>')
def track_open(token):
    """Track email opens via tracking pixel"""
    try:
        # Rate limiting to prevent abuse
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limit_check(f"open_{client_ip}", limit=30, window=60):
            return '', 429  # Too Many Requests

        # Find the campaign target by token
        campaign_target = CampaignTarget.query.filter_by(unique_token=token).first()
        if not campaign_target:
            return '', 404

        # Check if we already tracked an open from this target
        existing_open = EmailEvent.query.filter_by(
            campaign_target_id=campaign_target.id,
            event_type='opened'
        ).first()

        if existing_open:
            # Return pixel but don't create duplicate event
            return send_tracking_pixel()

        # Log the open event
        event = EmailEvent(
            campaign_target_id=campaign_target.id,
            event_type='opened',
            ip_address=client_ip,
            user_agent=request.headers.get('User-Agent'),
            metadata={
                'referer': request.headers.get('Referer'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        )

        db.session.add(event)

        # Update campaign target status
        if campaign_target.status == 'sent':
            campaign_target.status = 'opened'

        db.session.commit()

        # Return tracking pixel
        return send_tracking_pixel()

    except Exception as e:
        db.session.rollback()
        return '', 500

@tracking_bp.route('/click/<token>')
def track_click(token):
    """Track link clicks and redirect to training page"""
    try:
        # Rate limiting
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limit_check(f"click_{client_ip}", limit=20, window=60):
            return '', 429

        # Find the campaign target by token
        campaign_target = CampaignTarget.query.filter_by(unique_token=token).first()
        if not campaign_target:
            return render_template('errors/404.html'), 404

        # Check if we already tracked a click from this target
        existing_click = EmailEvent.query.filter_by(
            campaign_target_id=campaign_target.id,
            event_type='clicked'
        ).first()

        if not existing_click:
            # Log the click event
            event = EmailEvent(
                campaign_target_id=campaign_target.id,
                event_type='clicked',
                ip_address=client_ip,
                user_agent=request.headers.get('User-Agent'),
                metadata={
                    'referer': request.headers.get('Referer'),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            )

            db.session.add(event)

            # Update campaign target status
            if campaign_target.status in ['sent', 'opened']:
                campaign_target.status = 'clicked'

            db.session.commit()

        # Get campaign and template information for the training page
        campaign = Campaign.query.get(campaign_target.campaign_id)
        if not campaign:
            return render_template('errors/404.html'), 404

        # Get phishing indicators from template
        phishing_indicators = extract_phishing_indicators(campaign.template)

        # Render training page
        return render_template('phishing/training_page.html',
                             target=campaign_target.target,
                             campaign=campaign,
                             phishing_indicators=phishing_indicators,
                             submit_token=token)

    except Exception as e:
        db.session.rollback()
        return render_template('errors/500.html'), 500

@tracking_bp.route('/submit/<token>', methods=['POST'])
def track_submission(token):
    """Track form submissions (without storing actual credentials)"""
    try:
        # Rate limiting
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limit_check(f"submit_{client_ip}", limit=10, window=300):
            return jsonify({'error': 'Too many submissions'}), 429

        # Find the campaign target by token
        campaign_target = CampaignTarget.query.filter_by(unique_token=token).first()
        if not campaign_target:
            return jsonify({'error': 'Invalid token'}), 404

        # Check if we already tracked a submission from this target
        existing_submission = EmailEvent.query.filter_by(
            campaign_target_id=campaign_target.id,
            event_type='submitted'
        ).first()

        if not existing_submission:
            # Log the submission event (DO NOT STORE CREDENTIALS)
            event = EmailEvent(
                campaign_target_id=campaign_target.id,
                event_type='submitted',
                ip_address=client_ip,
                user_agent=request.headers.get('User-Agent'),
                metadata={
                    'form_data_received': True,  # Just flag that we got data
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'user_agent_hash': hash(request.headers.get('User-Agent', ''))
                    # NEVER store actual passwords or sensitive data
                }
            )

            db.session.add(event)

            # Update campaign target status
            campaign_target.status = 'submitted'

            db.session.commit()

        # Log successful phishing detection
        log_audit('PHISHING_SUBMITTED', 'campaign_target', campaign_target.id,
                 {'campaign_id': campaign_target.campaign_id})

        # Return success response for training page
        return jsonify({
            'success': True,
            'message': 'Thank you for participating in this security awareness training.',
            'next_step': 'education'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'An error occurred'}), 500

@tracking_bp.route('/education')
def education():
    """Additional educational resources page"""
    return render_template('phishing/education.html')

@tracking_bp.route('/quiz')
def quiz():
    """Interactive quiz page"""
    return render_template('phishing/quiz.html')

@tracking_bp.route('/feedback')
def feedback():
    """Feedback page for training effectiveness"""
    return render_template('phishing/feedback.html')

def send_tracking_pixel():
    """Return a 1x1 transparent PNG pixel"""
    try:
        pixel_path = os.path.join('static', 'images', 'pixel.png')
        if os.path.exists(pixel_path):
            return send_file(pixel_path, mimetype='image/png')
        else:
            # Fallback: return minimal PNG data
            import base64
            # 1x1 transparent PNG
            pixel_data = base64.b64decode(
                b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
            )
            from flask import Response
            return Response(pixel_data, mimetype='image/png')
    except Exception:
        return '', 500

def extract_phishing_indicators(template):
    """Extract potential phishing indicators from template for education"""
    indicators = []

    content = template.html_content.lower()
    subject = template.subject.lower()

    # Check for urgency indicators
    urgency_words = ['urgent', 'immediate', 'action required', 'immediately', 'hurry', 'limited time']
    for word in urgency_words:
        if word in content or word in subject:
            indicators.append({
                'type': 'Urgency',
                'description': f'Creates false urgency: "{word}"',
                'severity': 'high'
            })

    # Check for threat indicators
    threat_words = ['suspend', 'terminate', 'delete', 'close account', 'security alert', 'unusual activity']
    for word in threat_words:
        if word in content or word in subject:
            indicators.append({
                'type': 'Threat',
                'description': f'Contains threat language: "{word}"',
                'severity': 'high'
            })

    # Check for generic greetings
    generic_greetings = ['dear user', 'dear customer', 'hello user', 'valued customer']
    for greeting in generic_greetings:
        if greeting in content:
            indicators.append({
                'type': 'Generic Greeting',
                'description': f'Uses generic greeting: "{greeting}"',
                'severity': 'medium'
            })

    # Check for suspicious links
    import re
    # Look for URLs with suspicious patterns
    url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+'
    urls = re.findall(url_pattern, content)

    for url in urls:
        # Check for suspicious domain indicators
        if any(suspicious in url for suspicious in ['bit.ly', 'tinyurl', 'short.link']):
            indicators.append({
                'type': 'Suspicious Link',
                'description': f'Contains URL shortener: {url}',
                'severity': 'high'
            })
        elif any(suspicious in url for suspicious in ['secure-', 'verify-', 'account-', 'login-']):
            indicators.append({
                'type': 'Suspicious Link',
                'description': f'Contains security-themed URL: {url}',
                'severity': 'medium'
            })

    # Check for mismatched sender information
    if 'security' in subject and 'verification' in content:
        indicators.append({
            'type': 'Sender Mismatch',
            'description': 'Claims to be from security team but requires verification via link',
            'severity': 'high'
        })

    # If no indicators found, add generic ones
    if not indicators:
        indicators = [
            {
                'type': 'Suspicious Email',
                'description': 'This email contains elements commonly found in phishing attempts',
                'severity': 'medium'
            }
        ]

    return indicators

def hash(text):
    """Create a simple hash for user agent (not for security, just for deduplication)"""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:16]