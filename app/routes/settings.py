"""
Settings routes for EzTaskRunner.
Handles application settings and configuration.
"""
import os
import json
import logging
from flask import Blueprint, request, render_template, flash, redirect, url_for, current_app, jsonify

# Create blueprint
settings_bp = Blueprint('settings', __name__, url_prefix='')

@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    """Show and update application settings."""
    logger = logging.getLogger("EzTaskRunner")
    
    if request.method == "POST":
        try:
            # Update email notification settings
            enable_email = 'enable_email' in request.form
            smtp_host = request.form.get('smtp_host', '')
            smtp_port = request.form.get('smtp_port', '2525')
            smtp_user = request.form.get('smtp_user', '')
            smtp_pass = request.form.get('smtp_pass', '')
            email_sender = request.form.get('email_sender', '')
            email_recipients = request.form.get('email_recipients', '')
            
            # Get logging settings
            log_level = request.form.get('log_level', 'INFO')
            
            # Validate settings
            try:
                smtp_port = int(smtp_port)
                if smtp_port < 1 or smtp_port > 65535:
                    raise ValueError("Port must be between 1 and 65535")
            except ValueError:
                flash("Invalid SMTP port. Please enter a valid port number.", "error")
                return redirect(url_for('settings.settings'))
            
            # Validate log level
            valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if log_level not in valid_log_levels:
                log_level = 'INFO'  # Default to INFO if invalid
            
            # Save settings to environment variables (these will be lost on application restart)
            # In a production app, you'd want to save these to a config file
            os.environ['EMAIL_NOTIFICATIONS_ENABLED'] = str(enable_email)
            os.environ['EMAIL_SMTP_HOST'] = smtp_host
            os.environ['EMAIL_SMTP_PORT'] = str(smtp_port)
            os.environ['EMAIL_SMTP_USER'] = smtp_user
            os.environ['EMAIL_SMTP_PASS'] = smtp_pass
            os.environ['EMAIL_SENDER'] = email_sender
            os.environ['EMAIL_RECIPIENTS'] = email_recipients
            os.environ['LOG_LEVEL'] = log_level
            
            # Update application config
            current_app.config['EMAIL_NOTIFICATIONS_ENABLED'] = enable_email
            current_app.config['EMAIL_SMTP_HOST'] = smtp_host
            current_app.config['EMAIL_SMTP_PORT'] = smtp_port
            current_app.config['EMAIL_SMTP_USER'] = smtp_user
            current_app.config['EMAIL_SMTP_PASS'] = smtp_pass
            current_app.config['EMAIL_SENDER'] = email_sender
            current_app.config['EMAIL_RECIPIENTS'] = email_recipients.split(',')
            current_app.config['LOG_LEVEL'] = log_level
            
            # Reconfigure logging with the new log level
            log_level_const = getattr(logging, log_level, logging.INFO)
            
            # Update root logger
            logging.getLogger().setLevel(log_level_const)
            
            # Update app loggers
            logging.getLogger('EzTaskRunner').setLevel(log_level_const)
            logging.getLogger('EzTaskRunner.Tasks').setLevel(log_level_const)
            logging.getLogger('EzTaskRunner.Tools').setLevel(log_level_const)
            
            logger.info(f"Settings updated. Log level set to {log_level}")
            flash("Settings updated successfully.", "success")
            return redirect(url_for('settings.settings'))
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}")
            flash(f"Error updating settings: {str(e)}", "error")
            return redirect(url_for('settings.settings'))
    
    # Display settings page
    return render_template(
        'settings.html',
        config=current_app.config,
        title="Settings"
    )

@settings_bp.route("/test_email", methods=["POST"])
def test_email():
    """Send a test email using the provided configuration."""
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        # Get settings from request body
        data = request.json or {}
        smtp_host = data.get('smtp_host', current_app.config.get('EMAIL_SMTP_HOST'))
        smtp_port = int(data.get('smtp_port', current_app.config.get('EMAIL_SMTP_PORT')))
        smtp_user = data.get('smtp_user', current_app.config.get('EMAIL_SMTP_USER'))
        smtp_pass = data.get('smtp_pass', current_app.config.get('EMAIL_SMTP_PASS'))
        sender = data.get('email_sender', current_app.config.get('EMAIL_SENDER'))
        recipients_str = data.get('email_recipients', ','.join(current_app.config.get('EMAIL_RECIPIENTS', [])))
        
        # Parse recipients
        recipients = [r.strip() for r in recipients_str.split(',') if r.strip()]
        if not recipients:
            return jsonify({"success": False, "error": "No recipients specified"})
        
        # Send test email
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from datetime import datetime
        
        # Create message
        msg = MIMEMultipart()
        msg['Subject'] = f"EzTaskRunner Test Email - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg['From'] = sender
        msg['To'] = ', '.join(recipients)
        
        # Create email body
        html_body = f"""
        <html>
        <body>
            <h2>EzTaskRunner Test Email</h2>
            <p>This is a test email from EzTaskRunner to verify your email notification settings.</p>
            
            <h3>Current Configuration:</h3>
            <ul>
                <li><strong>SMTP Host:</strong> {smtp_host}</li>
                <li><strong>SMTP Port:</strong> {smtp_port}</li>
                <li><strong>Sender:</strong> {sender}</li>
                <li><strong>Recipients:</strong> {recipients_str}</li>
                <li><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
            </ul>
            
            <p>If you received this email, your email notification settings are working correctly!</p>
        </body>
        </html>
        """
        
        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        logger.info(f"Test email sent successfully to {recipients_str}")
        return jsonify({"success": True})
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error sending test email: {error_msg}")
        return jsonify({"success": False, "error": error_msg}) 