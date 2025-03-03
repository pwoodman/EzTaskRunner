"""
Task manager module for EzTaskRunner.

Handles task storage, retrieval, and management.
"""
import os
import json
import logging
import importlib
from pathlib import Path
from datetime import datetime, timedelta
import time
from typing import Dict, Any, List, Optional
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from flask import current_app

# Get loggers
logger = logging.getLogger("EzTaskRunner")
tasks_logger = logging.getLogger("EzTaskRunner.Tasks")
tools_logger = logging.getLogger("EzTaskRunner.Tools")

# Constants
MAX_WORKERS = min(os.cpu_count() or 4, 8)  # Use CPU count up to a maximum of 8 workers
MAX_MEMORY_PERCENT = 85.0  # Maximum memory usage percentage

# Locks and executors
task_executor = ThreadPoolExecutor(
    max_workers=MAX_WORKERS,
    thread_name_prefix="TaskExecutor"
)
task_lock = Lock()

# In-memory task store
tasks = {}

def add_task_to_store(job_id: str, task_data: Dict[str, Any]) -> None:
    """
    Add a task to the task store.
    
    Args:
        job_id: The job ID
        task_data: The task data dictionary
    """
    logger = logging.getLogger("EzTaskRunner")
    with task_lock:
        tasks[job_id] = task_data
    
    # Save to disk if task storage is enabled
    try:
        tasks_dir = current_app.config.get('TASKS_DIR')
        if tasks_dir:
            os.makedirs(tasks_dir, exist_ok=True)
            task_file = Path(tasks_dir) / f"{job_id}.json"
            with open(task_file, 'w') as f:
                json.dump(task_data, f, indent=2)
            logger.info(f"Task {job_id} saved to disk")
    except Exception as e:
        logger.error(f"Error saving task to disk: {str(e)}")

def get_task(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a task from the task store.
    
    Args:
        job_id: The job ID
        
    Returns:
        The task data dictionary or None if not found
    """
    # Check in-memory store first
    with task_lock:
        if job_id in tasks:
            return tasks[job_id]
    
    # Try to load from disk
    try:
        from flask import current_app
        
        try:
            tasks_dir = current_app.config.get('TASKS_DIR')
        except RuntimeError:  # Working outside of application context
            from app import app
            with app.app_context():
                tasks_dir = current_app.config.get('TASKS_DIR')
                
        if tasks_dir:
            task_file = Path(tasks_dir) / f"{job_id}.json"
            if task_file.exists():
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                with task_lock:
                    tasks[job_id] = task_data
                return task_data
    except Exception as e:
        logging.getLogger("EzTaskRunner").error(f"Error loading task from disk: {str(e)}")
    
    return None

def update_task(job_id: str, task_data: Dict[str, Any]) -> bool:
    """
    Update a task in the task store.
    
    Args:
        job_id: The job ID
        task_data: The updated task data dictionary
        
    Returns:
        bool: Whether the update was successful
    """
    logger = logging.getLogger("EzTaskRunner")
    
    # Check if task exists
    with task_lock:
        if job_id not in tasks:
            logger.warning(f"Attempted to update non-existent task: {job_id}")
            return False
        
        # Update the task
        tasks[job_id].update(task_data)
    
    # Save to disk if task storage is enabled
    try:
        tasks_dir = current_app.config.get('TASKS_DIR')
        if tasks_dir:
            task_file = Path(tasks_dir) / f"{job_id}.json"
            with open(task_file, 'w') as f:
                with task_lock:
                    json.dump(tasks[job_id], f, indent=2)
            logger.info(f"Task {job_id} updated and saved to disk")
            
            # Update the task in the scheduler if enabled
            with task_lock:
                task_info = tasks[job_id]
                
            # Update the scheduler if the task is enabled
            if task_info.get('enabled', True):
                try:
                    # Get the scheduler
                    scheduler = current_app.config.get('SCHEDULER')
                    if not scheduler:
                        logger.warning("Scheduler not found in app config, task will not be scheduled")
                        return True
                    
                    # Remove the existing job if it exists
                    try:
                        scheduler.remove_job(job_id)
                        logger.info(f"Removed existing job from scheduler: {job_id}")
                    except:
                        # Job may not exist in the scheduler yet, which is fine
                        pass
                    
                    # Create the appropriate trigger based on the task's trigger type
                    trigger_type = task_info.get('trigger_type')
                    if not trigger_type:
                        logger.warning(f"No trigger type for task {job_id}, not scheduling")
                        return True
                    
                    if trigger_type == 'date':
                        from apscheduler.triggers.date import DateTrigger
                        run_date_str = task_info.get('run_date')
                        if not run_date_str:
                            logger.warning(f"No run date for date trigger in task {job_id}")
                            return True
                            
                        # Parse the date string
                        from datetime import datetime
                        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
                            try:
                                run_date = datetime.strptime(run_date_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            logger.warning(f"Invalid date format for task {job_id}: {run_date_str}")
                            return True
                            
                        trigger = DateTrigger(run_date=run_date)
                        
                    elif trigger_type == 'interval':
                        from apscheduler.triggers.interval import IntervalTrigger
                        interval_days = int(task_info.get('interval_days', 0))
                        interval_hours = int(task_info.get('interval_hours', 0))
                        interval_minutes = int(task_info.get('interval_minutes', 0))
                        
                        if interval_days == 0 and interval_hours == 0 and interval_minutes == 0:
                            logger.warning(f"Invalid interval for task {job_id}")
                            return True
                            
                        trigger = IntervalTrigger(
                            days=interval_days,
                            hours=interval_hours,
                            minutes=interval_minutes
                        )
                        
                    elif trigger_type == 'cron':
                        from apscheduler.triggers.cron import CronTrigger
                        cron_expr = task_info.get('cron_expression')
                        if not cron_expr:
                            logger.warning(f"No cron expression for task {job_id}")
                            return True
                            
                        try:
                            # Try to parse as a proper cron expression
                            minute, hour, day, month, day_of_week = cron_expr.split()
                            trigger = CronTrigger(
                                minute=minute,
                                hour=hour,
                                day=day,
                                month=month,
                                day_of_week=day_of_week
                            )
                        except ValueError:
                            logger.warning(f"Invalid cron expression for task {job_id}: {cron_expr}")
                            return True
                    else:
                        logger.warning(f"Unsupported trigger type for task {job_id}: {trigger_type}")
                        return True
                    
                    # Register the task with the scheduler
                    from app.utils.task_helpers import run_task
                    logger.info(f"Registering updated task {job_id} with the scheduler using trigger type {trigger_type}")
                    scheduler.add_job(
                        func=run_task,
                        trigger=trigger,
                        args=[job_id],
                        id=job_id
                    )
                    
                    logger.info(f"Task {job_id} successfully registered with scheduler")
                except Exception as e:
                    logger.error(f"Error updating task in scheduler: {str(e)}")
            else:
                # If task is disabled, remove it from the scheduler
                try:
                    scheduler = current_app.config.get('SCHEDULER')
                    if scheduler:
                        try:
                            scheduler.remove_job(job_id)
                            logger.info(f"Removed disabled task from scheduler: {job_id}")
                        except:
                            # Job may not exist in the scheduler, which is fine
                            pass
                except Exception as e:
                    logger.error(f"Error removing disabled task from scheduler: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error updating task: {str(e)}")
        return False
        
    return True

def delete_task_from_store(job_id: str) -> bool:
    """
    Delete a task from the task store.
    
    Args:
        job_id: The job ID
        
    Returns:
        True if successful, False otherwise
    """
    logger = logging.getLogger("EzTaskRunner")
    
    # Remove from scheduler
    try:
        scheduler = current_app.config.get('SCHEDULER')
        if scheduler:
            scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id} from scheduler")
    except Exception as e:
        logger.warning(f"Error removing job from scheduler: {str(e)}")
    
    # Remove from memory
    with task_lock:
        if job_id in tasks:
            del tasks[job_id]
    
    # Remove from disk
    try:
        tasks_dir = current_app.config.get('TASKS_DIR')
        if tasks_dir:
            task_file = Path(tasks_dir) / f"{job_id}.json"
            if task_file.exists():
                task_file.unlink()
                logger.info(f"Deleted task file for {job_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting task file: {str(e)}")
        return False

def get_all_tasks() -> List[Dict[str, Any]]:
    """
    Get all tasks.
    
    Returns:
        A list of task data dictionaries
    """
    tasks_dir = current_app.config['TASKS_DIR'].resolve()
    if not tasks_dir.exists():
        return []
    
    tasks = []
    for task_file in tasks_dir.glob('*.json'):
        try:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
                
                # Ensure script_type is populated for existing tasks
                if 'script_type' not in task_data and 'script_path' in task_data:
                    from pathlib import Path
                    script_path = task_data['script_path']
                    file_ext = Path(script_path).suffix.lower()
                    if file_ext == '.py':
                        task_data['script_type'] = 'python'
                    elif file_ext == '.ps1':
                        task_data['script_type'] = 'powershell'
                    elif file_ext in ['.bat', '.cmd']:
                        task_data['script_type'] = 'batch'
                    else:
                        task_data['script_type'] = 'unknown'
                
                tasks.append(task_data)
        except Exception as e:
            logger.error(f"Error loading task from {task_file}: {e}")
    
    return tasks

def load_tasks_from_disk() -> None:
    """Load all tasks from disk and populate the in-memory store."""
    import logging
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        # Get the tasks directory from the Flask app config
        try:
            from flask import current_app
            tasks_dir = current_app.config.get('TASKS_DIR')
        except RuntimeError:  # Working outside of application context
            from app import app
            with app.app_context():
                tasks_dir = current_app.config.get('TASKS_DIR')
        
        if not tasks_dir or not os.path.exists(tasks_dir):
            logger.warning("Tasks directory not found or not specified")
            return
        
        # Load all task files
        files_loaded = 0
        for task_file in Path(tasks_dir).glob("*.json"):
            try:
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                
                if "job_id" in task_data:
                    job_id = task_data["job_id"]
                else:
                    # Use the filename as job ID if not specified in the task data
                    job_id = task_file.stem
                    task_data["job_id"] = job_id
                
                with task_lock:
                    tasks[job_id] = task_data
                files_loaded += 1
            except Exception as e:
                logger.error(f"Error loading task file {task_file}: {str(e)}")
        
        logger.info(f"Loaded {files_loaded} tasks from disk")
        
        # Check for tasks that might be stuck in RUNNING state
        try:
            cleanup_running_tasks()
        except Exception as e:
            logger.error(f"Error during cleanup of running tasks: {str(e)}")

        # Register all loaded tasks with the scheduler
        register_tasks_with_scheduler()
    except Exception as e:
        logger.error(f"Error loading tasks from disk: {str(e)}")
        # Don't raise the exception to avoid app startup failures

def register_tasks_with_scheduler():
    """Register all enabled tasks with the scheduler."""
    logger = logging.getLogger("EzTaskRunner")
    registered_count = 0
    
    try:
        # Get the scheduler from the Flask app config
        try:
            from flask import current_app
            scheduler = current_app.config.get('SCHEDULER')
        except RuntimeError:  # Working outside of application context
            from app import app
            with app.app_context():
                scheduler = current_app.config.get('SCHEDULER')
        
        if not scheduler:
            logger.warning("Scheduler not found in app config")
            return
            
        # Clear existing jobs first to avoid duplicates
        scheduler.remove_all_jobs()
        
        # Register each enabled task
        with task_lock:
            for job_id, task_data in tasks.items():
                # Skip disabled tasks
                if not task_data.get('enabled', True):
                    logger.info(f"Skipping disabled task: {job_id}")
                    continue
                
                try:
                    # Create the appropriate trigger based on the task's trigger type
                    trigger_type = task_data.get('trigger_type')
                    if not trigger_type:
                        logger.warning(f"No trigger type for task {job_id}, skipping")
                        continue
                    
                    if trigger_type == 'date':
                        from apscheduler.triggers.date import DateTrigger
                        # Parse the run_date string into a datetime object
                        run_date_str = task_data.get('run_date')
                        if not run_date_str:
                            logger.warning(f"No run date for date trigger in task {job_id}, skipping")
                            continue
                            
                        from datetime import datetime
                        # Try different formats
                        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
                            try:
                                run_date = datetime.strptime(run_date_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            logger.warning(f"Invalid date format for task {job_id}: {run_date_str}, skipping")
                            continue
                            
                        trigger = DateTrigger(run_date=run_date)
                        
                    elif trigger_type == 'interval':
                        from apscheduler.triggers.interval import IntervalTrigger
                        # Get interval parameters
                        interval_days = int(task_data.get('interval_days', 0))
                        interval_hours = int(task_data.get('interval_hours', 0))
                        interval_minutes = int(task_data.get('interval_minutes', 0))
                        
                        if interval_days == 0 and interval_hours == 0 and interval_minutes == 0:
                            logger.warning(f"Invalid interval for task {job_id}, skipping")
                            continue
                            
                        trigger = IntervalTrigger(
                            days=interval_days,
                            hours=interval_hours,
                            minutes=interval_minutes
                        )
                        
                    elif trigger_type == 'cron':
                        from apscheduler.triggers.cron import CronTrigger
                        # Get cron parameters
                        cron_expr = task_data.get('cron_expression')
                        if not cron_expr:
                            logger.warning(f"No cron expression for task {job_id}, skipping")
                            continue
                            
                        try:
                            # Try to parse as a proper cron expression
                            minute, hour, day, month, day_of_week = cron_expr.split()
                            trigger = CronTrigger(
                                minute=minute,
                                hour=hour,
                                day=day,
                                month=month,
                                day_of_week=day_of_week
                            )
                        except ValueError:
                            logger.warning(f"Invalid cron expression for task {job_id}: {cron_expr}, skipping")
                            continue
                    else:
                        logger.warning(f"Unsupported trigger type for task {job_id}: {trigger_type}, skipping")
                        continue
                    
                    # Register the task with the scheduler
                    from app.utils.task_helpers import run_task
                    logger.info(f"Registering task {job_id} with the scheduler using trigger type {trigger_type}")
                    scheduler.add_job(
                        func=run_task,
                        trigger=trigger,
                        args=[job_id],
                        id=job_id
                    )
                    registered_count += 1
                    
                except Exception as e:
                    logger.error(f"Error registering task {job_id} with scheduler: {str(e)}")
                    
        logger.info(f"Registered {registered_count} tasks with the scheduler")
        
    except Exception as e:
        logger.error(f"Error registering tasks with scheduler: {str(e)}")

def cleanup_running_tasks() -> None:
    """Check for tasks that are stuck in RUNNING or QUEUED state and fix their status."""
    import logging
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        # Make sure we have tasks loaded first
        if not tasks:
            logger.info("No tasks to check for running status.")
            return
            
        running_tasks_count = 0
        queued_tasks_count = 0
        fixed_tasks_count = 0
        
        task_items = []
        with task_lock:
            # Create a copy of the tasks items to avoid modifying during iteration
            task_items = list(tasks.items())
            
        # Get current time for checking task duration
        current_time = datetime.now()
        
        for job_id, task in task_items:
            # Check for both RUNNING and QUEUED tasks
            if task.get("status") in ["RUNNING", "QUEUED"]:
                if task.get("status") == "RUNNING":
                    running_tasks_count += 1
                else:  # QUEUED
                    queued_tasks_count += 1
                    
                process_id = task.get("process_id")
                
                # Check if the task was just started (within the last 5 seconds)
                # This prevents marking tasks as failed if they're just starting up
                recently_started = False
                if "last_run" in task:
                    try:
                        last_run_time = parse_datetime_str(task["last_run"])
                        time_diff = current_time - last_run_time
                        recently_started = time_diff.total_seconds() < 5  # 5 second grace period
                        
                        if recently_started:
                            logger.info(f"Not cleaning up task {job_id} as it was recently started ({time_diff.total_seconds():.1f} seconds ago)")
                            continue  # Skip this task as it was just started
                    except Exception as e:
                        logger.warning(f"Could not parse last_run time for task {job_id}: {str(e)}")
                
                # For QUEUED tasks, check if they've been queued too long (more than 30 seconds)
                if task.get("status") == "QUEUED":
                    if "last_run" in task:
                        try:
                            last_run_time = parse_datetime_str(task["last_run"])
                            time_diff = current_time - last_run_time
                            if time_diff.total_seconds() > 30:  # 30 second timeout for queued tasks
                                logger.warning(f"Task {job_id} has been queued for {time_diff.total_seconds():.1f} seconds, marking as failed")
                                task["status"] = "FAILED"
                                task["last_error"] = "Task marked as failed: stuck in QUEUED state for too long"
                                update_task(job_id, task)
                                fixed_tasks_count += 1
                        except Exception as e:
                            logger.warning(f"Could not parse last_run time for queued task {job_id}: {str(e)}")
                    continue
                
                # For RUNNING tasks, check if the process is still running
                # Check if the process is actually running
                if process_id:
                    try:
                        import psutil
                        if not psutil.pid_exists(int(process_id)):
                            # Process is not running, update status
                            task["status"] = "FAILED"
                            task["last_error"] = "Task marked as failed at startup: process not found"
                            update_task(job_id, task)
                            fixed_tasks_count += 1
                            logger.warning(f"Fixed stuck task: {job_id} (process {process_id} not running)")
                    except Exception as e:
                        logger.error(f"Error checking process {process_id} for task {job_id}: {str(e)}")
                        # Only mark as failed if the task wasn't recently started
                        if not recently_started:
                            task["status"] = "FAILED"
                            task["last_error"] = f"Failed to check process status: {str(e)}"
                            update_task(job_id, task)
                            fixed_tasks_count += 1
                else:
                    # No process ID, just mark as failed
                    task["status"] = "FAILED"
                    task["last_error"] = "Task marked as failed at startup: no process ID"
                    update_task(job_id, task)
                    fixed_tasks_count += 1
                    logger.warning(f"Fixed stuck task: {job_id} (no process ID)")
        
        if running_tasks_count > 0 or queued_tasks_count > 0:
            logger.info(f"Found {running_tasks_count} tasks in RUNNING state, {queued_tasks_count} in QUEUED state, fixed {fixed_tasks_count}")
    except Exception as e:
        logger.error(f"Error cleaning up running tasks: {str(e)}")
        # Don't re-raise the exception to avoid app startup failures

def get_task_history(job_id: str) -> List[Dict[str, Any]]:
    """
    Get the execution history for a task.
    
    Args:
        job_id: The job ID
        
    Returns:
        List of execution history entries
    """
    logger = logging.getLogger("EzTaskRunner")
    history = []
    try:
        from flask import current_app
        
        try:
            history_dir = current_app.config.get('TASK_HISTORY_DIR')
        except RuntimeError:  # Working outside of application context
            from app import app
            with app.app_context():
                history_dir = current_app.config.get('TASK_HISTORY_DIR')
                
        if not history_dir:
            return history
            
        history_dir_path = Path(history_dir)
        if not history_dir_path.exists():
            return history
            
        for history_file in history_dir_path.glob(f"{job_id}_*.json"):
            try:
                with open(history_file, 'r') as f:
                    history.append(json.load(f))
            except Exception as e:
                logger.error(f"Error reading history file {history_file}: {str(e)}")
                
        # Sort by timestamp
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    except Exception as e:
        logger.error(f"Error getting task history: {str(e)}")
        
    return history

def parse_datetime_str(dt_str: str) -> datetime:
    """
    Parse a datetime string into a datetime object.
    
    Args:
        dt_str: The datetime string in the format "YYYY-MM-DD HH:MM:SS"
        
    Returns:
        A datetime object
    """
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

def run_task(job_id: str) -> Dict[str, Any]:
    """
    Run a task.
    
    Args:
        job_id: The job ID
        
    Returns:
        The execution result
    """
    tasks_logger.info(f"Task execution started - Job ID: {job_id}")
    
    from app.utils import run_script, get_system_metrics
    from flask import current_app
    from datetime import datetime, timedelta
    import time
    
    # Get the Flask application instance
    from app import app
    
    with app.app_context():
        # Make sure we get the latest task data from disk/store
        task = get_task(job_id)
        if not task:
            tasks_logger.error(f"Task execution failed - Job ID: {job_id} - Task not found")
            return {"success": False, "error": f"Task {job_id} not found"}
        
        # Check if task is enabled
        if task.get("enabled", True) is False:
            tasks_logger.info(f"Task execution skipped - Job ID: {job_id} - Task is disabled")
            return {"success": False, "error": "Task is disabled"}
        
        script_path = task.get("script_path")
        if not script_path:
            tasks_logger.error(f"Task execution failed - Job ID: {job_id} - No script path specified")
            return {"success": False, "error": "No script path specified"}
        
        # Get max runtime
        max_runtime = task.get("max_runtime", 60)  # Default to 60 minutes if not specified
        
        # Check if this is a retry attempt
        current_retry_count = task.get("current_retry_count", 0)
        
        # Check if the task is already running (to prevent duplicate runs)
        if task.get("status") == "RUNNING" and task.get("process_id"):
            # Check if the process is actually still running
            try:
                import psutil
                process_id = task.get("process_id")
                if process_id and psutil.pid_exists(int(process_id)):
                    tasks_logger.warning(f"Task is already running - Job ID: {job_id} - Process ID: {process_id}")
                    return {"success": False, "error": "Task is already running"}
                else:
                    tasks_logger.warning(f"Task was marked as running but process is not active - Job ID: {job_id} - Process ID: {process_id}")
                    # Process is not running, update status to indicate it may have crashed
                    task["status"] = "FAILED"
                    task["last_error"] = "Task process is not running but was marked as RUNNING - it may have crashed"
                    update_task(job_id, task)
            except Exception as e:
                tasks_logger.error(f"Error checking process status - Job ID: {job_id} - Error: {str(e)}")
        
        # Update task status - transition from any state (including QUEUED) to RUNNING
        tasks_logger.info(f"Transitioning task from state '{task.get('status', 'UNKNOWN')}' to 'RUNNING'")
        task["status"] = "RUNNING"
        task["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # If this is a retry, log it
        if current_retry_count > 0:
            tasks_logger.info(f"This is retry attempt {current_retry_count} for task {job_id}")
        
        # Clear any previous error if this is the first attempt (not a retry)
        if current_retry_count == 0 and "last_error" in task:
            task.pop("last_error", None)
            
        # Clear process ID to start fresh
        task["process_id"] = None
        
        # Update task in store to show as RUNNING during the buffer period
        update_task(job_id, task)
        
        # Buffer period: Wait 10 seconds and check system resources
        tasks_logger.info(f"Starting 10-second buffer period for task {job_id} to check system resources")
        
        # Store resource metrics for the task history
        resource_check = {
            "buffer_time_start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_percent_ok": False,
            "memory_percent_ok": False,
            "can_proceed": False
        }
        
        # Sleep for 10 seconds, checking system resources
        buffer_end_time = datetime.now() + timedelta(seconds=10)
        while datetime.now() < buffer_end_time:
            # Check system metrics
            metrics = get_system_metrics()
            
            # Log current resource usage
            cpu_percent = metrics.get('cpu_percent', 100)  # Default to 100% if not available
            memory_percent = metrics.get('memory_percent', 100)  # Default to 100% if not available
            
            tasks_logger.info(f"Buffer check for task {job_id}: CPU: {cpu_percent}%, Memory: {memory_percent}%")
            
            # Store the metrics
            resource_check["cpu_percent"] = cpu_percent
            resource_check["memory_percent"] = memory_percent
            resource_check["cpu_percent_ok"] = cpu_percent < 75
            resource_check["memory_percent_ok"] = memory_percent < 90
            
            # Wait a bit before checking again
            time.sleep(2)
        
        # Check final resource status
        resource_check["buffer_time_end"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not resource_check["cpu_percent_ok"]:
            tasks_logger.warning(f"CPU usage too high ({resource_check['cpu_percent']}%) for task {job_id}, but proceeding anyway")
        
        if not resource_check["memory_percent_ok"]:
            tasks_logger.warning(f"Memory usage too high ({resource_check['memory_percent']}%) for task {job_id}, but proceeding anyway")
        
        # We always proceed for now, just log the warnings
        resource_check["can_proceed"] = True
        tasks_logger.info(f"Buffer period complete for task {job_id}. CPU: {resource_check['cpu_percent']}%, Memory: {resource_check['memory_percent']}%")
        
        # Run the script
        tasks_logger.info(f"Task running script - Job ID: {job_id} - Script: {script_path}")
        result = run_script(
            script_path, 
            job_id=job_id,
            history_dir=current_app.config["TASK_HISTORY_DIR"],
            max_runtime_minutes=max_runtime,  # Pass the max runtime to the run_script function
            buffer_metrics=resource_check  # Pass the buffer metrics
        )
        
        # Add resource metrics to result
        result["buffer_resource_check"] = resource_check
        
        # Get the task again to ensure we have the latest version
        # This is important because another process might have updated the task status
        task = get_task(job_id)
        if not task:
            tasks_logger.error(f"Task not found after execution - Job ID: {job_id}")
            return result
        
        # Ensure the result has valid fields
        if result is None:
            tasks_logger.error(f"Run script returned None for task {job_id}")
            result = {"success": False, "error": "Script execution returned no result"}
        
        # Make sure we have the success field defined
        if "success" not in result:
            tasks_logger.warning(f"Success field missing in result for task {job_id}")
            # Default to True if the result exists but has no success field
            result["success"] = True
            
        # Only update the status if the task is still in RUNNING state
        # This prevents overwriting potential changes made by other processes
        if task.get("status") == "RUNNING":
            # Store the process ID in the task if available
            if result.get("process_id"):
                task["process_id"] = result["process_id"]
                update_task(job_id, task)
                tasks_logger.info(f"Task process ID stored - Job ID: {job_id} - Process ID: {result['process_id']}")
            
            # Handle auto-retry logic if the task failed
            if not result.get("success", False):
                error_message = result.get("error", "Unknown error")[:500]  # Limit size of error message
                task["last_error"] = error_message
                
                # Check if auto-retry is enabled
                auto_retry_enabled = task.get("auto_retry_enabled", False)
                max_retry_attempts = task.get("retry_attempts", 3)
                retry_interval = task.get("retry_interval", 5)
                
                if auto_retry_enabled and current_retry_count < max_retry_attempts:
                    # Increment retry count
                    task["current_retry_count"] = current_retry_count + 1
                    tasks_logger.info(f"Task {job_id} failed, scheduling retry {task['current_retry_count']} of {max_retry_attempts}")
                    
                    # Calculate retry time (current time + retry interval in minutes)
                    retry_time = datetime.now() + timedelta(minutes=retry_interval)
                    task["next_retry_time"] = retry_time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Set task status to indicate it's waiting for retry
                    task["status"] = "FAILED"  # Still mark as failed for now
                    
                    try:
                        # Get the scheduler
                        scheduler = current_app.config.get('SCHEDULER')
                        if scheduler:
                            # Create a one-time trigger for the retry
                            from apscheduler.triggers.date import DateTrigger
                            trigger = DateTrigger(run_date=retry_time)
                            
                            # Add the job to the scheduler
                            retry_job_id = f"{job_id}_retry_{task['current_retry_count']}"
                            from app.utils.task_helpers import run_task as schedule_task
                            scheduler.add_job(
                                func=schedule_task,
                                trigger=trigger,
                                args=[job_id],
                                id=retry_job_id,
                                replace_existing=True
                            )
                            tasks_logger.info(f"Retry job {retry_job_id} added to scheduler")
                            
                    except Exception as e:
                        tasks_logger.error(f"Error scheduling retry for task {job_id}: {str(e)}")
                    
                    # Update task in store
                    update_task(job_id, task)
                else:
                    if auto_retry_enabled and current_retry_count >= max_retry_attempts:
                        tasks_logger.info(f"Task {job_id} failed, maximum retry attempts ({max_retry_attempts}) reached")
                    
                    # Mark as failed if retry is disabled or max retries reached
                    task["status"] = "FAILED"
                    
                    # If email notifications are configured and enabled, send failure notification
                    try:
                        if current_app.config.get('EMAIL_NOTIFICATIONS_ENABLED', False) and task.get('email_notifications_enabled', True):
                            from app.utils.email_notifier import send_task_failure_email
                            send_task_failure_email(task, error_message)
                    except Exception as e:
                        tasks_logger.error(f"Error sending email notification for task {job_id}: {str(e)}")
                    
                    # Update task in store
                    update_task(job_id, task)
            else:
                # Task succeeded
                task["status"] = "SUCCESS"
                # Clear error message if task succeeded
                if "last_error" in task:
                    task.pop("last_error", None)
                
                # Reset retry count for next run
                if "current_retry_count" in task:
                    task["current_retry_count"] = 0
                
                # Clear process ID when task is complete
                task["process_id"] = None
                
                # Update task in store
                update_result = update_task(job_id, task)
                if not update_result:
                    tasks_logger.error(f"Failed to update task {job_id} status to {task['status']}")
                else:
                    tasks_logger.info(f"Successfully updated task {job_id} status to {task['status']}")
        else:
            tasks_logger.info(f"Not updating task status as it is no longer in RUNNING state - Job ID: {job_id} - Current status: {task.get('status')}")
            
            # Fix for manually run tasks: If the task was successful but status wasn't updated
            # This handles cases where the status might get changed by another process
            if result.get("success", False) and task.get("status") != "SUCCESS":
                tasks_logger.info(f"Task {job_id} completed successfully but status is {task.get('status')}, updating to SUCCESS")
                task["status"] = "SUCCESS"
                # Clear any error messages
                if "last_error" in task:
                    task.pop("last_error", None)
                # Update the task
                update_task(job_id, task)
        
        # Log the completion status
        if result.get("success", False):
            tasks_logger.info(f"Task completed successfully - Job ID: {job_id} - Execution time: {result.get('execution_time', 0):.2f}s")
        else:
            tasks_logger.error(f"Task failed - Job ID: {job_id} - Error: {result.get('error', 'Unknown error')[:200]}...")
        
        return result

def stop_task(job_id: str) -> Dict[str, Any]:
    """
    Stop a running task.
    
    Args:
        job_id: The job ID of the task to stop
        
    Returns:
        dict: Results of the operation
    """
    tasks_logger.info(f"Attempting to stop task - Job ID: {job_id}")
    
    from app.utils import kill_task
    
    result = {
        "success": False,
        "message": "",
        "error": None
    }
    
    task = get_task(job_id)
    if not task:
        result["error"] = f"Task {job_id} not found"
        tasks_logger.error(f"Task stop failed - Job ID: {job_id} - Task not found")
        return result
    
    # Check if the task is running
    if task.get("status") != "RUNNING" or not task.get("process_id"):
        result["error"] = f"Task {job_id} is not currently running or has no process ID"
        tasks_logger.warning(f"Task stop skipped - Job ID: {job_id} - Task not running")
        return result
    
    # Kill the process
    process_id = task.get("process_id")
    kill_result = kill_task(process_id)
    
    if kill_result.get("success"):
        # Update task status
        task["status"] = "STOPPED"
        task["process_id"] = None
        update_task(job_id, task)
        
        result["success"] = True
        result["message"] = kill_result.get("message", f"Task {job_id} stopped successfully")
        tasks_logger.info(f"Task stopped successfully - Job ID: {job_id} - Process ID: {process_id}")
    else:
        result["error"] = kill_result.get("error", "Unknown error stopping task")
        tasks_logger.error(f"Task stop failed - Job ID: {job_id} - Error: {result['error']}")
    
    return result
