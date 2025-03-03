"""
Core module for EzTaskRunner.
Handles Flask application setup and configuration.
"""
import logging
import os
from pathlib import Path
from flask import Flask, render_template, flash, g, redirect, url_for
from datetime import datetime

from app.scheduler import init_scheduler
from app.version import __version__

def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configure the application
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-for-development-only'),
        # Use raw strings for path defaults to avoid Unicode escape issues on Windows
        SCRIPTS_DIR=Path(os.environ.get('SCRIPTS_DIR', r'scripts')).resolve(),
        LOG_DIR=Path(os.environ.get('LOG_DIR', r'logs')).resolve(),
        TASK_HISTORY_DIR=Path(os.environ.get('TASK_HISTORY_DIR', r'task_history')).resolve(),
        TASKS_DIR=Path(os.environ.get('TASKS_DIR', r'tasks')).resolve(),
        
        # Email notification settings
        EMAIL_NOTIFICATIONS_ENABLED=os.environ.get('EMAIL_NOTIFICATIONS_ENABLED', 'False').lower() == 'true',
        EMAIL_SMTP_HOST=os.environ.get('EMAIL_SMTP_HOST', 'sandbox.smtp.mailtrap.io'),
        EMAIL_SMTP_PORT=int(os.environ.get('EMAIL_SMTP_PORT', 2525)),
        EMAIL_SMTP_USER=os.environ.get('EMAIL_SMTP_USER', '72c8025da81b94'),
        EMAIL_SMTP_PASS=os.environ.get('EMAIL_SMTP_PASS', '0e03c13c3eba5c'),
        EMAIL_SENDER=os.environ.get('EMAIL_SENDER', 'EzTaskRunner <eztaskrunner@example.com>'),
        EMAIL_RECIPIENTS=os.environ.get('EMAIL_RECIPIENTS', 'admin@example.com').split(','),
        SERVER_NAME=os.environ.get('SERVER_NAME', None),  # Needed for url_for with _external=True
        
        # Logging settings
        LOG_LEVEL=os.environ.get('LOG_LEVEL', 'INFO'),  # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
        
        # Version information
        VERSION=__version__
    )
    
    # Ensure required directories exist
    os.makedirs(app.config['SCRIPTS_DIR'], exist_ok=True)
    os.makedirs(app.config['LOG_DIR'], exist_ok=True)
    os.makedirs(app.config['TASK_HISTORY_DIR'], exist_ok=True)
    os.makedirs(app.config['TASKS_DIR'], exist_ok=True)
    
    # Configure logging
    setup_logging(app)
    
    # Initialize scheduler
    scheduler = init_scheduler(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Add template filters
    @app.template_filter('parse_datetime')
    def parse_datetime_filter(value):
        """Parse datetime string to datetime object."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    
    @app.template_filter('split')
    def split_filter(value, delimiter=None):
        """Split a string by delimiter."""
        if not isinstance(value, str):
            return []
        return value.split(delimiter)
    
    # Add context processor for template globals
    @app.context_processor
    def inject_globals():
        """Inject global variables into templates."""
        return {
            'now': datetime.now()
        }
    
    return app

def setup_logging(app):
    """Set up logging for the application."""
    log_dir = app.config['LOG_DIR']
    
    # Get the configured log level from app config
    log_level_name = app.config.get('LOG_LEVEL', 'INFO')
    
    # Convert string log level to logging constant
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    
    # Create specific log files
    main_log_file = log_dir / 'eztaskrunner.log'
    tools_log_file = log_dir / 'tools.log'
    errors_log_file = log_dir / 'errors.log'
    tasks_log_file = log_dir / 'tasks.log'
    
    # Set up formatting
    standard_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    detailed_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s')
    
    # Configure root logger with main log file and console output
    root_handler = logging.FileHandler(main_log_file)
    root_handler.setFormatter(standard_formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(standard_formatter)
    
    # Create tools logger handler
    tools_handler = logging.FileHandler(tools_log_file)
    tools_handler.setFormatter(standard_formatter)
    
    # Create error logger handler with more detailed formatting
    errors_handler = logging.FileHandler(errors_log_file)
    errors_handler.setLevel(logging.ERROR)
    errors_handler.setFormatter(detailed_formatter)
    
    # Create tasks logger handler
    tasks_handler = logging.FileHandler(tasks_log_file)
    tasks_handler.setFormatter(standard_formatter)
    
    # Set up root logger with main handlers
    logging.basicConfig(
        level=log_level,  # Use the configured log level
        handlers=[root_handler, console_handler, errors_handler]
    )
    
    # Create and configure application logger
    app_logger = logging.getLogger('EzTaskRunner')
    app_logger.setLevel(log_level)  # Use the configured log level
    app_logger.addHandler(tools_handler)
    
    # Create and configure tasks logger
    tasks_logger = logging.getLogger('EzTaskRunner.Tasks')
    tasks_logger.setLevel(log_level)  # Use the configured log level
    tasks_logger.addHandler(tasks_handler)
    
    # Create and configure tools logger
    tools_logger = logging.getLogger('EzTaskRunner.Tools')
    tools_logger.setLevel(log_level)  # Use the configured log level
    tools_logger.propagate = False  # Don't propagate to root logger
    tools_logger.addHandler(tools_handler)
    
    # Log initial message
    app_logger.info(f"Logging system initialized with log level {log_level_name} and separate logs for tools, errors, and tasks")
    
    # Reduce verbosity of some loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

def register_blueprints(app):
    """Register all application blueprints."""
    # Import tasks blueprint
    from app.routes.tasks import tasks_bp
    
    # Import files blueprint
    from app.routes.files import files_bp
    
    # Import monitoring blueprint
    from app.routes.monitoring import monitoring_bp
    
    # Import settings blueprint
    from app.routes.settings import settings_bp
    
    # Register blueprints
    app.register_blueprint(tasks_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(settings_bp)
    
    # Register additional routes
    @app.route('/')
    def index():
        return redirect(url_for('tasks.index'))

def register_error_handlers(app):
    """Register error handlers for the application."""
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500)
    def internal_server_error(e):
        logger = logging.getLogger('EzTaskRunner')
        logger.error(f"Internal server error: {str(e)}")
        return render_template('errors/500.html'), 500 