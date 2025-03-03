"""
Email notification module for EzTaskRunner.

Handles sending email notifications for task failures and other events.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import url_for, current_app

logger = logging.getLogger("EzTaskRunner")

def send_task_failure_email(task, error_message, task_history_entry=None):
    """
    Send an email notification when a task fails.
    
    Args:
        task: The task data dictionary
        error_message: The error message to include in the email
        task_history_entry: Optional task history entry with additional details
        
    Returns:
        bool: True if the email was sent successfully, False otherwise
    """
    try:
        # Get email configuration from app config
        config = current_app.config
        
        email_config = {
            'enabled': config.get('EMAIL_NOTIFICATIONS_ENABLED', False),
            'smtp_host': config.get('EMAIL_SMTP_HOST', 'sandbox.smtp.mailtrap.io'),
            'smtp_port': config.get('EMAIL_SMTP_PORT', 2525),
            'smtp_user': config.get('EMAIL_SMTP_USER', '72c8025da81b94'),
            'smtp_pass': config.get('EMAIL_SMTP_PASS', '0e03c13c3eba5c'),
            'sender': config.get('EMAIL_SENDER', 'EzTaskRunner <eztaskrunner@example.com>'),
            'recipients': config.get('EMAIL_RECIPIENTS', ['admin@example.com'])
        }
        
        # Check if global email notifications are enabled
        if not email_config['enabled']:
            logger.info(f"Global email notifications are disabled. Would have sent notification for task: {task['job_id']}")
            return False
            
        # Check if task-specific email notifications are enabled
        if not task.get('email_notifications_enabled', True):  # Default to True for backward compatibility
            logger.info(f"Task-specific email notifications are disabled for task: {task['job_id']}")
            return False
            
        # Create task details
        task_name = task.get('task_name', 'Unknown Task')
        job_id = task.get('job_id', 'unknown')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create email subject
        subject = f"Task: {task_name} Failed - {timestamp}"
        
        # Create email recipients
        # If recipients is a string, convert to list
        recipients = email_config['recipients']
        if isinstance(recipients, str):
            recipients = [recipients]
            
        # Create multipart message
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = email_config['sender']
        msg['To'] = ', '.join(recipients)
        
        # Create email body with HTML formatting
        html_body = f"""
        <html>
        <body>
            <h2>Task Failure Notification</h2>
            <p>A task has failed in EzTaskRunner.</p>
            
            <h3>Task Details:</h3>
            <ul>
                <li><strong>Task Name:</strong> {task_name}</li>
                <li><strong>Job ID:</strong> {job_id}</li>
                <li><strong>Failure Time:</strong> {timestamp}</li>
                <li><strong>Script:</strong> {task.get('script_path', 'N/A')}</li>
            </ul>
            
            <h3>Error Message:</h3>
            <pre style="background-color: #f8d7da; padding: 10px; border-radius: 5px;">{error_message}</pre>
        """
        
        # Add history URL if in app context
        try:
            history_url = url_for('tasks.view_task_history', job_id=job_id, _external=True)
            html_body += f"""
            <p>
                <a href="{history_url}" style="display: inline-block; padding: 10px 15px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">
                    View Task History
                </a>
            </p>
            """
        except Exception as e:
            logger.warning(f"Could not generate task history URL: {str(e)}")
            
        html_body += """
        </body>
        </html>
        """
        
        # Attach HTML body
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email via SMTP
        with smtplib.SMTP(email_config['smtp_host'], email_config['smtp_port']) as server:
            server.starttls()
            server.login(email_config['smtp_user'], email_config['smtp_pass'])
            server.send_message(msg)
            
        logger.info(f"Sent failure notification email for task {task_name} ({job_id})")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        return False 