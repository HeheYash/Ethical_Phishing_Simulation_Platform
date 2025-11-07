from flask import current_app, url_for
from flask_mail import Message, Mail
from database.models import Campaign, CampaignTarget, Target, Template, EmailEvent
from utils.helpers import generate_tracking_url, render_template_content
from utils.security import log_audit
from datetime import datetime, timezone
from app import db
import time
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Initialize Flask-Mail
mail = Mail()

class EmailSender:
    """Email sending service for phishing campaigns"""

    def __init__(self, campaign=None):
        self.campaign = campaign
        self.rate_limit = current_app.config.get('MAX_EMAILS_PER_HOUR', 100)
        self.sent_count = 0
        self.start_time = time.time()

    def send_campaign_emails(self, campaign_id):
        """Send all emails for a campaign (to be run as background task)"""
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            current_app.logger.error(f"Campaign {campaign_id} not found")
            return False

        self.campaign = campaign
        campaign_targets = CampaignTarget.query.filter_by(
            campaign_id=campaign_id,
            status='pending'
        ).all()

        total_targets = len(campaign_targets)
        current_app.logger.info(f"Starting email send for campaign {campaign_id} to {total_targets} targets")

        success_count = 0
        error_count = 0

        for i, campaign_target in enumerate(campaign_targets):
            try:
                # Rate limiting
                if not self.check_rate_limit():
                    current_app.logger.warning(f"Rate limit reached, waiting...")
                    time.sleep(60)  # Wait 1 minute

                success = self.send_email_to_target(campaign_target)
                if success:
                    success_count += 1
                    campaign_target.status = 'sent'
                    campaign_target.sent_at = datetime.now(timezone.utc)
                else:
                    error_count += 1

                # Commit progress every 10 emails
                if (i + 1) % 10 == 0:
                    db.session.commit()
                    current_app.logger.info(f"Sent {i + 1}/{total_targets} emails for campaign {campaign_id}")

            except Exception as e:
                error_count += 1
                current_app.logger.error(f"Error sending email to target {campaign_target.id}: {str(e)}")
                # Log error event
                self.log_error_event(campaign_target, str(e))

        # Final commit
        db.session.commit()

        # Update campaign status if all emails processed
        if success_count + error_count == total_targets:
            # Check if there are still pending targets
            remaining = CampaignTarget.query.filter_by(
                campaign_id=campaign_id,
                status='pending'
            ).count()

            if remaining == 0:
                # Campaign sending complete
                campaign.status = 'completed'
                campaign.completed_at = datetime.now(timezone.utc)

        # Log campaign completion
        log_audit('CAMPAIGN_EMAILS_SENT', 'campaign', campaign_id, {
            'total_targets': total_targets,
            'success_count': success_count,
            'error_count': error_count
        })

        current_app.logger.info(f"Campaign {campaign_id} email send completed: {success_count} success, {error_count} errors")
        return success_count > 0

    def send_email_to_target(self, campaign_target):
        """Send phishing email to a specific target"""
        try:
            # Get target and template
            target = campaign_target.target
            template = self.campaign.template

            # Prepare template variables
            variables = self.prepare_template_variables(target, campaign_target)

            # Render email content
            subject = render_template_content(template.subject, variables)
            html_content = render_template_content(template.html_content, variables)

            # Add security watermark
            html_content = self.add_security_watermark(html_content)

            # Send email using Flask-Mail
            success = self.send_email_flask_mail(target.email, subject, html_content)

            if success:
                # Log sent event
                self.log_sent_event(campaign_target)
                self.sent_count += 1
                return True
            else:
                return False

        except Exception as e:
            current_app.logger.error(f"Error sending email to {target.email}: {str(e)}")
            return False

    def send_email_flask_mail(self, to_email, subject, html_content):
        """Send email using Flask-Mail"""
        try:
            with current_app.app_context():
                msg = Message(
                    subject=subject,
                    sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
                    recipients=[to_email]
                )
                msg.html = html_content

                mail.send(msg)
                return True

        except Exception as e:
            current_app.logger.error(f"Flask-Mail error: {str(e)}")
            # Fallback to direct SMTP
            return self.send_email_direct_smtp(to_email, subject, html_content)

    def send_email_direct_smtp(self, to_email, subject, html_content):
        """Fallback: Send email using direct SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER')
            msg['To'] = to_email

            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Connect to SMTP server
            smtp_server = current_app.config.get('MAIL_SERVER')
            smtp_port = current_app.config.get('MAIL_PORT', 587)
            use_tls = current_app.config.get('MAIL_USE_TLS', True)
            username = current_app.config.get('MAIL_USERNAME')
            password = current_app.config.get('MAIL_PASSWORD')

            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()

            if username and password:
                server.login(username, password)

            server.send_message(msg)
            server.quit()

            return True

        except Exception as e:
            current_app.logger.error(f"Direct SMTP error: {str(e)}")
            return False

    def prepare_template_variables(self, target, campaign_target):
        """Prepare template variables for email rendering"""
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')

        variables = {
            'first_name': target.first_name or 'User',
            'last_name': target.last_name or '',
            'email': target.email,
            'department': target.department or 'Unknown',
            'company': 'Your Company',  # Could be made configurable
            'campaign_name': self.campaign.name,
            'sender_name': 'IT Security Team',  # Could be made configurable
            'sender_email': current_app.config.get('MAIL_DEFAULT_SENDER'),
            'tracking_number': campaign_target.unique_token[:8].upper(),
            'click_url': generate_tracking_url(campaign_target.unique_token, 'click', base_url),
            'tracking_pixel': f'<img src="{generate_tracking_url(campaign_target.unique_token, "open", base_url)}" width="1" height="1" style="display:none;" alt="tracking pixel">'
        }

        return variables

    def add_security_watermark(self, content):
        """Add security watermark to all outgoing emails"""
        watermark = '''
        <div style="background-color: #fff3cd; color: #856404; padding: 10px; margin: 20px 0; border: 1px solid #ffeaa7; border-radius: 4px; text-align: center; font-size: 12px;">
            ⚠️ <strong>SECURITY TRAINING TEST</strong> - This is a simulated phishing email for security awareness training.
        </div>
        '''
        return watermark + content

    def check_rate_limit(self):
        """Check if we're within rate limits"""
        # Check hourly rate limit
        elapsed = time.time() - self.start_time
        if elapsed < 3600:  # Within first hour
            return self.sent_count < self.rate_limit
        else:
            # Reset counter for new hour
            self.start_time = time.time()
            self.sent_count = 0
            return True

    def log_sent_event(self, campaign_target):
        """Log email sent event"""
        event = EmailEvent(
            campaign_target_id=campaign_target.id,
            event_type='sent',
            ip_address='127.0.0.1',  # Server IP
            metadata={
                'server_time': datetime.now(timezone.utc).isoformat(),
                'campaign_name': self.campaign.name,
                'template_name': self.campaign.template.name
            }
        )

        db.session.add(event)

    def log_error_event(self, campaign_target, error_message):
        """Log email sending error"""
        event = EmailEvent(
            campaign_target_id=campaign_target.id,
            event_type='bounced',
            metadata={
                'error': error_message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        )

        db.session.add(event)

def queue_campaign_emails(campaign):
    """Queue campaign for sending (typically runs in background)"""
    try:
        sender = EmailSender(campaign)

        # Run in background thread (in production, use Celery or similar)
        thread = threading.Thread(
            target=sender.send_campaign_emails,
            args=(campaign.id,)
        )
        thread.daemon = True
        thread.start()

        current_app.logger.info(f"Campaign {campaign.id} queued for background sending")
        return True

    except Exception as e:
        current_app.logger.error(f"Error queuing campaign emails: {str(e)}")
        return False

def send_test_email(email_address, template_id):
    """Send a test email for preview purposes"""
    try:
        template = Template.query.get(template_id)
        if not template:
            return False

        # Create a fake target for testing
        from database.models import Target, Campaign, CampaignTarget
        import uuid

        # Create test target if not exists
        target = Target.query.filter_by(email=email_address).first()
        if not target:
            target = Target(
                email=email_address,
                first_name='Test',
                last_name='User',
                department='IT'
            )
            db.session.add(target)
            db.session.commit()

        # Create a test campaign and target association
        test_campaign = Campaign.query.filter_by(name='TEST_CAMPAIGN').first()
        if not test_campaign:
            test_campaign = Campaign(
                name='TEST_CAMPAIGN',
                description='Test campaign for email previews',
                template_id=template_id,
                status='draft',
                created_by=1
            )
            db.session.add(test_campaign)
            db.session.commit()

        # Create campaign target
        campaign_target = CampaignTarget(
            campaign_id=test_campaign.id,
            target_id=target.id,
            unique_token=uuid.uuid4().hex,
            status='pending'
        )
        db.session.add(campaign_target)
        db.session.commit()

        # Send test email
        sender = EmailSender(test_campaign)
        success = sender.send_email_to_target(campaign_target)

        # Clean up test data (optional)
        # db.session.delete(campaign_target)
        # db.session.commit()

        return success

    except Exception as e:
        current_app.logger.error(f"Error sending test email: {str(e)}")
        return False