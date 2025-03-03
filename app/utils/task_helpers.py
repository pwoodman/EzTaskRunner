"""
Task helper functions for EzTaskRunner.

This module contains utilities for handling tasks and script paths.
"""
import os
import logging
from datetime import datetime
from pathlib import Path
from flask import current_app

# Get specialized loggers
logger = logging.getLogger("EzTaskRunner")
tools_logger = logging.getLogger("EzTaskRunner.Tools")

def parse_datetime(dt_str: str) -> datetime:
    """
    Parse a datetime string into a datetime object.
    
    Args:
        dt_str: The datetime string
        
    Returns:
        A datetime object
        
    Raises:
        ValueError: If the string cannot be parsed
    """
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError("Invalid datetime format. Expected format: YYYY-MM-DDTHH:MM or YYYY-MM-DD HH:MM:SS")

def validate_script_path(script_path: str) -> str:
    """
    Validate that a script path is safe and points to a valid script file within the scripts directory.
    Supports Python (.py), PowerShell (.ps1), and Batch (.bat, .cmd) files.
    
    Args:
        script_path: The path to the script, relative to the scripts directory
        
    Returns:
        The absolute path to the script if valid
        
    Raises:
        ValueError: If the path is invalid or unsafe
    """
    tools_logger.info(f"Validating script path: {script_path}")
    
    if not script_path:
        tools_logger.warning("Empty script path provided")
        raise ValueError("Script path cannot be empty")
    
    # Get the scripts directory
    scripts_dir = current_app.config['SCRIPTS_DIR'].resolve()
    
    # Clean the path and resolve it
    try:
        # First check if it's a relative path (from the scripts directory)
        script_file = (scripts_dir / script_path).resolve()
        
        # Ensure the path is inside the scripts directory (prevent directory traversal)
        if not str(script_file).startswith(str(scripts_dir)):
            tools_logger.warning(f"Security: Attempted directory traversal: {script_path}")
            raise ValueError("Invalid script path: outside of scripts directory")
        
        # Check if it's a supported file type
        valid_extensions = ['.py', '.ps1', '.bat', '.cmd']
        if script_file.suffix.lower() not in valid_extensions:
            tools_logger.warning(f"Invalid file type: {script_path} (supported types: {', '.join(valid_extensions)})")
            raise ValueError(f"Invalid script: not a supported file type (supported: {', '.join(valid_extensions)})")
        
        # Check if file exists
        if not script_file.exists():
            tools_logger.warning(f"File not found: {script_path}")
            raise ValueError(f"Script file does not exist: {script_path}")
        
        tools_logger.info(f"Script path validated successfully: {script_path} → {script_file}")
        return str(script_file)
    except Exception as e:
        if not isinstance(e, ValueError):
            tools_logger.error(f"Error validating script path: {script_path} - {str(e)}")
            raise ValueError(f"Invalid script path: {str(e)}")
        raise

def run_task(job_id: str) -> None:
    """
    Run a task with the given job ID.
    
    This function is called by the scheduler when a job is triggered.
    
    Args:
        job_id: The job ID to run
    """
    # Import directly when needed to avoid circular imports
    from app.task_manager import run_task as tm_run_task, task_executor
    
    # Submit the task to the ThreadPoolExecutor instead of creating a new thread
    # This gives better control over thread management and ensures proper process isolation
    task_executor.submit(tm_run_task, job_id)
    
    # Return immediately, allowing the scheduler to continue processing other events
    return 