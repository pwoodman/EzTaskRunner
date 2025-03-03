"""
Monitoring routes for EzTaskRunner.
Handles system monitoring and logs viewing.
"""
import logging
from pathlib import Path
from flask import Blueprint, send_from_directory, request, flash, redirect, url_for, current_app, jsonify

# Create blueprint
monitoring_bp = Blueprint('monitoring', __name__, url_prefix='')

@monitoring_bp.route("/monitoring", methods=["GET"])
def monitoring_dashboard():
    """Show monitoring dashboard with system metrics and logs."""
    from app.views.monitoring import render_monitoring_dashboard
    return render_monitoring_dashboard()

@monitoring_bp.route("/download_log/<filename>")
def download_log(filename: str):
    """Download a specific log file."""
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        log_dir = current_app.config['LOG_DIR']
        return send_from_directory(log_dir, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading log file {filename}: {str(e)}")
        flash(f"Error downloading log file: {str(e)}", "danger")
        return redirect(url_for('monitoring.monitoring_dashboard'))

@monitoring_bp.route("/purge_logs", methods=["POST"])
def purge_logs():
    """Purge old log files."""
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        from app.utils import purge_logs as utils_purge_logs
        
        # Get days to keep from form
        days_to_keep = int(request.form.get('days_to_keep', 30))
        
        # Validate days_to_keep
        if days_to_keep < 1:
            flash("Days to keep must be at least 1", "danger")
            return redirect(url_for('monitoring.monitoring_dashboard'))
        
        # Get log directory
        log_dir = current_app.config['LOG_DIR']
        
        # Define files to always keep
        keep_files = ['eztaskrunner.log', 'tasks.log', 'errors.log']
        
        # Purge logs
        result = utils_purge_logs(log_dir, days_to_keep, keep_files)
        
        # Flash result
        if result['success']:
            flash(f"Successfully purged {result['purged_count']} log files older than {days_to_keep} days", "success")
        else:
            flash(f"Error purging logs: {result['error']}", "danger")
        
        return redirect(url_for('monitoring.monitoring_dashboard'))
    except Exception as e:
        logger.error(f"Error purging logs: {str(e)}")
        flash(f"Error purging logs: {str(e)}", "danger")
        return redirect(url_for('monitoring.monitoring_dashboard'))

@monitoring_bp.route("/api/metrics")
def get_metrics_json():
    """
    Return system metrics as JSON for AJAX requests.
    This endpoint is used by the monitoring dashboard for real-time updates.
    """
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        # Import necessary functions
        from app.utils import get_system_metrics
        from app.task_manager import get_all_tasks
        from datetime import datetime
        
        # Get system metrics
        metrics = get_system_metrics()
        
        # Get running tasks
        all_tasks = get_all_tasks()
        running_tasks = [task for task in all_tasks if task.get('status') == 'RUNNING']
        
        # Format active tasks for JSON response
        active_tasks = []
        for task in running_tasks:
            # Calculate duration if possible
            duration = None
            if task.get('last_run'):
                try:
                    last_run = datetime.fromisoformat(task['last_run'].replace('T', ' ').split('.')[0])
                    duration_seconds = (datetime.now() - last_run).total_seconds()
                    
                    if duration_seconds < 60:
                        duration = f"{int(duration_seconds)} seconds"
                    else:
                        duration = f"{int(duration_seconds // 60)} minutes"
                except Exception:
                    duration = "Unknown"
            
            active_tasks.append({
                'job_id': task.get('job_id'),
                'name': task.get('task_name'),
                'script': task.get('script_path'),
                'start_time': task.get('last_run'),
                'duration': duration
            })
        
        # Add active tasks to metrics
        metrics['active_tasks'] = active_tasks
        
        # Add timestamp
        metrics['timestamp'] = datetime.now().isoformat()
        
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error getting metrics JSON: {str(e)}")
        return jsonify({'error': str(e)}), 500 