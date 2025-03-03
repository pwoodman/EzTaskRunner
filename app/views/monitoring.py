"""
Monitoring views for EzTaskRunner.
Renders templates related to system monitoring and logs.
"""
import os
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from flask import render_template, current_app
import psutil

from app.utils import get_system_metrics, get_task_history, get_system_info
from app.task_manager import get_all_tasks

def _human_readable_size(size_bytes):
    """Convert bytes to a human-readable string."""
    if size_bytes < 0:
        raise ValueError("Negative size value")
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {units[i]}"

def render_monitoring_dashboard():
    """Render the monitoring dashboard with system metrics and log information."""
    # Get system metrics
    metrics = {}
    try:
        metrics = get_system_metrics()
        if not metrics or 'error' in metrics:
            # Just log the error without attempting to include it in the formatted string
            current_app.logger.error("Error getting system metrics")
    except Exception as e:
        # Use repr for safer logging and avoid f-strings for the error message
        current_app.logger.error("Exception getting system metrics: " + repr(e))
        metrics['error'] = "Error getting system metrics. Please check the logs for details."

    # Get tasks information for running tasks and recent failures
    running_tasks = []
    recent_failures_24h = []
    recent_failures_7d = []
    
    # Current datetime for template
    now = datetime.now()
    
    try:
        all_tasks = get_all_tasks()
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        
        for task in all_tasks:
            # Parse the last_run timestamp if available
            if task.get('last_run'):
                try:
                    last_run_dt = datetime.fromisoformat(task['last_run'])
                except (ValueError, TypeError):
                    # If parsing fails, try with a different format or skip
                    try:
                        last_run_dt = datetime.strptime(task['last_run'], "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        last_run_dt = None
            else:
                last_run_dt = None
            
            # Check for running tasks
            if task.get('status') == 'RUNNING':
                running_tasks.append(task)
            
            # Check for recent failures
            if task.get('status') == 'FAILED' and last_run_dt:
                if last_run_dt >= one_day_ago:
                    recent_failures_24h.append(task)
                elif last_run_dt >= seven_days_ago:
                    recent_failures_7d.append(task)
    except Exception as e:
        current_app.logger.error(f"Error getting task information: {str(e)}")

    # Get task execution history for the last 7 days
    recent_executions = []
    try:
        all_history = []
        for task in all_tasks:
            job_id = task.get('job_id')
            if job_id:
                task_history = get_task_history(job_id)
                for entry in task_history:
                    entry['task_name'] = task.get('task_name', 'Unknown Task')
                    entry['job_id'] = job_id  # Ensure job_id is in the history entry
                    all_history.append(entry)
        
        # Sort by timestamp and filter for last 7 days
        all_history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)
        
        for entry in all_history:
            try:
                if 'timestamp' in entry:
                    timestamp = entry['timestamp']
                    if 'T' in timestamp:
                        timestamp_dt = datetime.fromisoformat(timestamp)
                    else:
                        timestamp_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    
                    if timestamp_dt >= seven_days_ago:
                        recent_executions.append(entry)
            except (ValueError, TypeError) as e:
                current_app.logger.error(f"Error parsing timestamp: {str(e)}")
                
        # Limit to most recent 50 executions to prevent overwhelming the page
        recent_executions = recent_executions[:50]
    except Exception as e:
        current_app.logger.error(f"Error getting task execution history: {str(e)}")

    # Get log files
    log_files = []
    log_dir = Path(current_app.config['LOG_DIR'])
    
    try:
        if log_dir.exists():
            for file_path in log_dir.glob('*.log'):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    modified = datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    
                    log_files.append({
                        'name': file_path.name,
                        'size': size,
                        'size_human': _human_readable_size(size),
                        'modified': modified
                    })
            
            # Sort log files by modification time (most recent first)
            log_files.sort(key=lambda x: x['modified'], reverse=True)
    except Exception as e:
        current_app.logger.error(f"Error reading log files: {str(e)}")

    return render_template(
        'monitoring/dashboard.html',
        title='System Monitoring',
        metrics=metrics,
        log_files=log_files,
        running_tasks=running_tasks,
        recent_failures_24h=recent_failures_24h,
        recent_failures_7d=recent_failures_7d,
        recent_executions=recent_executions,
        now=now  # Pass current datetime to template
    ) 