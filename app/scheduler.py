"""
Scheduler module for EzTaskRunner.
Handles the background scheduler and job management.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore

def init_scheduler(app=None):
    """
    Initialize and configure the APScheduler.
    
    Args:
        app: Optional Flask application instance
        
    Returns:
        The configured BackgroundScheduler instance
    """
    logger = logging.getLogger("EzTaskRunner")
    logger.info("Initializing scheduler")
    
    # Configure job stores
    job_stores = {
        'default': MemoryJobStore()
    }
    
    # Create scheduler with 1 second check interval
    scheduler = BackgroundScheduler(
        jobstores=job_stores,
        job_defaults={
            'coalesce': True,  # Combine multiple executions into one
            'max_instances': 1  # Only one instance of each job can run at a time
        },
        # Set check interval to 1 second for more responsive job execution
        executor_opts={'check_interval': 1}
    )
    
    # Log scheduler settings
    logger.info("Scheduler check interval set to 1 second for responsive task execution")
    
    # Store scheduler in app config if app is provided
    if app is not None:
        app.config['SCHEDULER'] = scheduler
    
    # Start scheduler
    scheduler.start()
    logger.info("Scheduler initialized and started")
    
    return scheduler 