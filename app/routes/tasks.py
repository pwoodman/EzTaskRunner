"""
Tasks routes for EzTaskRunner.
Handles task creation, editing, deletion, and execution.
"""
import os
import uuid
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, current_app
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.utils.task_helpers import parse_datetime, validate_script_path, run_task
from app.utils.constants import STATUS_PENDING

# Create blueprint
tasks_bp = Blueprint('tasks', __name__, url_prefix='')

@tasks_bp.route("/", methods=["GET"])
def index():
    """Render the main dashboard."""
    from app.views.dashboard import render_dashboard
    return render_dashboard()

@tasks_bp.route("/add_task", methods=["GET", "POST"])
def add_task():
    """Add a new scheduled task."""
    logger = logging.getLogger("EzTaskRunner")
    
    if request.method == "POST":
        try:
            logger.info(f"Received add_task POST request with form data: {dict(request.form)}")
            raw_script_path = request.form.get("script_path")
            if not raw_script_path:
                logger.warning("Attempt to add task without script path")
                flash("Script path is required. Please select a script using the file browser.", "error")
                return redirect(url_for("tasks.add_task"))

            validated_script = validate_script_path(raw_script_path)
            logger.debug(f"Script path validation result: {validated_script} for path: {raw_script_path}")
            if not validated_script:
                logger.error(f"Invalid script path validation: {raw_script_path}")
                flash("Invalid script path. Please select a valid script file.", "error")
                return redirect(url_for("tasks.add_task"))

            task_name = request.form.get("task_name") or f"Task-{Path(validated_script).stem}"
            description = request.form.get("description") or ""
            trigger_type = request.form.get("trigger_type")
            
            # Get script type or determine it from file extension
            script_type = request.form.get("script_type")
            if not script_type:
                # Determine script type from file extension if not provided
                file_ext = Path(validated_script).suffix.lower()
                if file_ext == '.py':
                    script_type = 'python'
                elif file_ext == '.ps1':
                    script_type = 'powershell'
                elif file_ext in ['.bat', '.cmd']:
                    script_type = 'batch'
                else:
                    script_type = 'unknown'
            
            if not trigger_type:
                flash("Please select a trigger type (One-time, Interval, or Cron).", "error")
                return redirect(url_for("tasks.add_task"))

            job_id = str(uuid.uuid4())
            task_data: Dict[str, Any] = {
                "job_id": job_id,
                "task_name": task_name,
                "description": description,
                "script_path": validated_script,
                "script_type": script_type,  # Store the script type
                "trigger_type": trigger_type,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": STATUS_PENDING,
                "enabled": 'enabled' in request.form,  # Get enabled value from form
                "email_notifications_enabled": 'email_notifications' in request.form  # Get email notifications value from form
            }

            # Get max runtime in minutes
            max_runtime = request.form.get('max_runtime')
            if max_runtime and max_runtime.isdigit():
                task_data['max_runtime'] = int(max_runtime)
            else:
                task_data['max_runtime'] = 60  # Default to 60 minutes
                
            # Auto-retry settings
            task_data['auto_retry_enabled'] = 'auto_retry_enabled' in request.form
            
            # Get retry attempts
            retry_attempts = request.form.get('retry_attempts')
            if retry_attempts and retry_attempts.isdigit():
                retry_attempts = int(retry_attempts)
                # Ensure value is between 1-5
                task_data['retry_attempts'] = max(1, min(5, retry_attempts))
            else:
                task_data['retry_attempts'] = 3  # Default to 3 attempts
                
            # Get retry interval
            retry_interval = request.form.get('retry_interval')
            if retry_interval and retry_interval.isdigit():
                retry_interval = int(retry_interval)
                # Ensure value is between 1-60
                task_data['retry_interval'] = max(1, min(60, retry_interval))
            else:
                task_data['retry_interval'] = 5  # Default to 5 minutes
                
            # Initialize current retry count
            task_data['current_retry_count'] = 0

            scheduler = current_app.config['SCHEDULER']
            
            try:
                if trigger_type == "date":
                    schedule_time = request.form.get("schedule_time")
                    if not schedule_time:
                        raise ValueError("Schedule time is required for one-time tasks.")
                    run_time = parse_datetime(schedule_time)
                    if run_time <= datetime.now():
                        raise ValueError("Schedule time must be in the future.")
                    trigger = DateTrigger(run_date=run_time)
                    task_data["schedule_time"] = schedule_time

                elif trigger_type == "interval":
                    try:
                        hours = int(request.form.get("interval_hours") or 0)
                        minutes = int(request.form.get("interval_minutes") or 0)
                        seconds = int(request.form.get("interval_seconds") or 0)
                    except ValueError:
                        raise ValueError("Invalid interval values. Please enter valid numbers.")

                    if hours == 0 and minutes == 0 and seconds == 0:
                        raise ValueError("At least one interval value must be greater than 0.")
                    
                    if hours < 0 or minutes < 0 or seconds < 0:
                        raise ValueError("Interval values cannot be negative.")

                    if minutes >= 60 or seconds >= 60:
                        raise ValueError("Minutes and seconds must be less than 60.")

                    trigger = IntervalTrigger(hours=hours, minutes=minutes, seconds=seconds)
                    task_data["interval_hours"] = hours
                    task_data["interval_minutes"] = minutes
                    task_data["interval_seconds"] = seconds
                    task_data["schedule_time"] = f"Every {hours}h {minutes}m {seconds}s"

                elif trigger_type == "cron":
                    cron_expression = request.form.get("cron_expression")
                    if not cron_expression:
                        raise ValueError("Cron expression is required.")

                    parts = cron_expression.split()
                    if len(parts) != 5:
                        raise ValueError("Invalid cron expression format. Must have exactly 5 parts.")

                    try:
                        trigger = CronTrigger.from_crontab(cron_expression)
                        task_data["cron_expression"] = cron_expression
                        task_data["schedule_time"] = f"Cron: {cron_expression}"
                    except Exception as e:
                        raise ValueError(f"Invalid cron expression: {str(e)}")
                else:
                    raise ValueError(f"Unsupported trigger type: {trigger_type}")

                # Important: Use a function reference instead of a lambda to avoid memory leaks
                logger.info(f"Adding job {job_id} to scheduler with trigger {trigger}")
                scheduler.add_job(
                    func=run_task,
                    trigger=trigger,
                    args=[job_id],
                    id=job_id
                )
                
                # Add task to task manager
                from app.task_manager import add_task_to_store
                add_task_to_store(job_id, task_data)
                
                flash(f"Task '{task_name}' scheduled successfully!", "success")
                logger.info(f"Task '{task_name}' (ID: {job_id}) scheduled successfully")
                return redirect(url_for("tasks.index"))
                
            except ValueError as ve:
                flash(str(ve), "error")
                logger.warning(f"Validation error in add_task: {str(ve)}")
                return redirect(url_for("tasks.add_task"))
                
        except Exception as e:
            error_msg = str(e)
            stack_trace = traceback.format_exc()
            logger.error(f"Error in add_task: {error_msg}\n{stack_trace}")
            flash(f"An error occurred: {error_msg}", "error")
            return redirect(url_for("tasks.add_task"))
    else:
        from app.views.task_forms import render_add_task_form
        return render_add_task_form()


@tasks_bp.route("/edit_task/<job_id>", methods=["GET", "POST"])
def edit_task(job_id: str):
    """Edit an existing task."""
    logger = logging.getLogger("EzTaskRunner")
    
    from app.task_manager import get_task, update_task
    task = get_task(job_id)
    
    if not task:
        flash(f"Task with ID {job_id} not found.", "error")
        return redirect(url_for("tasks.index"))
    
    if request.method == "POST":
        try:
            # Similar to add_task but for editing
            task_name = request.form.get("task_name")
            description = request.form.get("description", "")
            
            # Update the task
            task["task_name"] = task_name
            task["description"] = description
            task["enabled"] = 'enabled' in request.form
            task["email_notifications_enabled"] = 'email_notifications' in request.form
            
            # Get max runtime
            max_runtime = request.form.get('max_runtime')
            if max_runtime and max_runtime.isdigit():
                task['max_runtime'] = int(max_runtime)
            
            # Auto-retry settings
            task['auto_retry_enabled'] = 'auto_retry_enabled' in request.form
            
            # Get retry attempts
            retry_attempts = request.form.get('retry_attempts')
            if retry_attempts and retry_attempts.isdigit():
                retry_attempts = int(retry_attempts)
                # Ensure value is between 1-5
                task['retry_attempts'] = max(1, min(5, retry_attempts))
            else:
                task['retry_attempts'] = 3  # Default to 3 attempts
                
            # Get retry interval
            retry_interval = request.form.get('retry_interval')
            if retry_interval and retry_interval.isdigit():
                retry_interval = int(retry_interval)
                # Ensure value is between 1-60
                task['retry_interval'] = max(1, min(60, retry_interval))
            else:
                task['retry_interval'] = 5  # Default to 5 minutes
            
            # Update in store
            update_task(job_id, task)
            
            flash(f"Task '{task_name}' updated successfully!", "success")
            return redirect(url_for("tasks.index"))
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error updating task: {error_msg}")
            flash(f"Error updating task: {error_msg}", "error")
            return redirect(url_for("tasks.edit_task", job_id=job_id))
    else:
        from app.views.task_forms import render_edit_task_form
        return render_edit_task_form(task)


@tasks_bp.route("/delete_task/<job_id>", methods=["POST"])
def delete_task(job_id: str):
    """Delete a task."""
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        from app.task_manager import delete_task_from_store
        success = delete_task_from_store(job_id)
        
        if success:
            flash("Task deleted successfully!", "success")
        else:
            flash("Task not found or could not be deleted.", "error")
            
        return redirect(url_for("tasks.index"))
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error deleting task: {error_msg}")
        flash(f"Error deleting task: {error_msg}", "error")
        return redirect(url_for("tasks.index"))


@tasks_bp.route("/run_task_now/<job_id>", methods=["POST"])
def run_task_now(job_id: str):
    """Run a task immediately."""
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        from app.task_manager import get_task, update_task, task_executor
        task = get_task(job_id)
        
        if not task:
            flash(f"Task with ID {job_id} not found.", "error")
            return redirect(url_for("tasks.index"))
        
        # Check if task is already running
        if task.get("status") == "RUNNING" and task.get("process_id"):
            try:
                import psutil
                process_id = task.get("process_id")
                if process_id and psutil.pid_exists(int(process_id)):
                    flash(f"Task '{task['task_name']}' is already running.", "warning")
                    return redirect(url_for("tasks.index"))
            except Exception as e:
                logger.error(f"Error checking process status: {str(e)}")
                # Continue with execution as if the task is not running
        
        # Update task status to indicate it's being queued
        task["status"] = "QUEUED"
        update_task(job_id, task)
        
        # Use task_executor to run the task as a background job
        from app.utils.task_helpers import run_task
        task_executor.submit(run_task, job_id)
        
        flash(f"Task '{task['task_name']}' queued for execution!", "success")
        return redirect(url_for("tasks.index"))
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error running task: {error_msg}")
        flash(f"Error running task: {error_msg}", "error")
        return redirect(url_for("tasks.index"))


@tasks_bp.route("/stop_task/<job_id>", methods=["POST"])
def stop_task_route(job_id: str):
    """Stop a running task."""
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        from app.task_manager import stop_task, get_task
        
        # Get the task first to get its name
        task = get_task(job_id)
        if not task:
            flash(f"Task with ID {job_id} not found.", "error")
            return redirect(url_for("tasks.index"))
        
        # Stop the task
        result = stop_task(job_id)
        
        if result.get("success"):
            flash(f"Task '{task['task_name']}' stopped successfully!", "success")
        else:
            error_msg = result.get("error", "Unknown error")
            flash(f"Error stopping task: {error_msg}", "warning")
        
        # Redirect to the referring page (either dashboard or tasks index)
        referrer = request.referrer
        if referrer and 'monitoring' in referrer:
            return redirect(url_for("monitoring.dashboard"))
        return redirect(url_for("tasks.index"))
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error stopping task: {error_msg}")
        flash(f"Error stopping task: {error_msg}", "error")
        return redirect(url_for("tasks.index"))


@tasks_bp.route("/task_history/<job_id>")
def view_task_history(job_id: str):
    """View the history of a task."""
    from app.task_manager import get_task, get_task_history
    task = get_task(job_id)
    
    if not task:
        flash(f"Task with ID {job_id} not found.", "error")
        return redirect(url_for("tasks.index"))
    
    history = get_task_history(job_id)
    from app.views.history import render_task_history
    return render_task_history(task, history)


@tasks_bp.route("/toggle_task/<job_id>", methods=["POST"])
def toggle_task(job_id: str):
    """Toggle a task's enabled/disabled status."""
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        from app.task_manager import get_task, update_task
        task = get_task(job_id)
        
        if not task:
            flash(f"Task with ID {job_id} not found.", "error")
            return redirect(url_for("tasks.index"))
        
        # Toggle the enabled status
        currently_enabled = task.get("enabled", True)
        task["enabled"] = not currently_enabled
        
        # Update the task
        success = update_task(job_id, task)
        
        if success:
            status_str = "disabled" if currently_enabled else "enabled"
            flash(f"Task '{task['task_name']}' {status_str} successfully!", "success")
        else:
            flash("Failed to update task status.", "error")
            
        return redirect(url_for("tasks.index"))
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error toggling task status: {error_msg}")
        flash(f"Error toggling task status: {error_msg}", "error")
        return redirect(url_for("tasks.index"))

def save_task():
    """Save a task."""
    try:
        task_data = {}
        job_id = request.form.get('job_id')
        task_data['name'] = request.form.get('name')
        task_data['description'] = request.form.get('description')
        # Check if task is enabled
        task_data['enabled'] = 'enabled' in request.form
        
        # Get max runtime in minutes
        max_runtime = request.form.get('max_runtime')
        if max_runtime and max_runtime.isdigit():
            task_data['max_runtime'] = int(max_runtime)
        else:
            task_data['max_runtime'] = 60  # Default to 60 minutes
        
        # Get the existing task to preserve script_path and other fields
        existing_task = get_task(job_id)
        if existing_task:
            # Preserve fields that shouldn't be changed
            task_data['script_path'] = existing_task.get('script_path')
            # Preserve schedule if present
            if 'trigger' in existing_task:
                task_data['trigger'] = existing_task.get('trigger')
        
        # Update the task
        update_task(job_id, task_data)
        
        flash(f"Task '{task_data['name']}' updated successfully!", "success")
        return redirect(url_for("tasks.index"))
    except Exception as e:
        error_msg = str(e)
        flash(f"Error updating task: {error_msg}", "error")
        return redirect(url_for("tasks.edit_task", job_id=job_id)) 