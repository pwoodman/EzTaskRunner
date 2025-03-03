"""
EzTaskRunner - A simple task scheduling application.

This package contains all application modules and serves as the application entry point.
"""
import logging
from app.core import create_app

# Create and configure the application instance
app = create_app()

# Set up logger
logger = logging.getLogger("EzTaskRunner")
logger.info("EzTaskRunner application initialized")

# Initialize tasks
with app.app_context():
    # Import here to avoid circular imports
    from app.task_manager import load_tasks_from_disk
    
    # Load tasks from disk (cleanup_running_tasks is called within this function)
    load_tasks_from_disk()