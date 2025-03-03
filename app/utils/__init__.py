"""
Utilities package for EzTaskRunner.
"""
import logging
from pathlib import Path
from datetime import datetime, timedelta
import json
import os
import time
import traceback
import importlib.util
import sys
import subprocess
import signal
import psutil  # Add this import for process management
import platform
import shutil  # Add this import for alternate disk usage measurement

# Import from task_helpers
from app.utils.task_helpers import (
    parse_datetime,
    validate_script_path,
    run_task
)

# Import from system_info
from app.utils.system_info import get_system_info

# Import from constants
from app.utils.constants import (
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_FAILED
)

def get_system_metrics():
    """
    Get system resource metrics.
    
    Returns:
        Dictionary with CPU, memory and disk usage information
    """
    # Initialize logger
    logger = logging.getLogger("EzTaskRunner")
    
    # Import psutil outside the try block to specifically check for import errors
    try:
        import psutil
    except ImportError as e:
        logger.error("Error importing psutil module: " + repr(e))
        return {'error': "Could not import psutil module. Make sure it's installed correctly."}
    
    metrics = {}
    
    # Get each metric in separate try blocks to identify the specific failing component
    try:
        # Get CPU usage
        metrics['cpu_percent'] = psutil.cpu_percent(interval=0.1)  # Reduced interval time
        logger.debug(f"Got CPU metrics: {metrics['cpu_percent']}%")
    except Exception as e:
        logger.error("Error getting CPU metrics: " + repr(e))
        return {'error': "Failed to retrieve CPU metrics. Please check the logs for details."}
    
    try:
        # Get memory usage
        memory = psutil.virtual_memory()
        metrics['memory_percent'] = memory.percent
        metrics['memory_available'] = memory.available
        metrics['memory_total'] = memory.total
        logger.debug(f"Got memory metrics: {metrics['memory_percent']}%")
    except Exception as e:
        logger.error("Error getting memory metrics: " + repr(e))
        return {'error': "Failed to retrieve memory metrics. Please check the logs for details."}
    
    try:
        # Get disk usage with BOTH shutil and psutil for better Windows compatibility
        # First try using shutil which is part of Python's standard library
        disk_paths_to_try = []
        
        # Build a list of paths to try based on OS
        if platform.system() == 'Windows':
            # On Windows, get all available drives
            system_drive = os.environ.get('SystemDrive', 'C:')
            # Try system drive first
            disk_paths_to_try.append((system_drive, f"system drive ({system_drive})"))
            
            # Add other drive letters if available (simpler approach for Windows)
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:"
                if os.path.exists(drive):
                    if drive != system_drive:  # Skip if we already added the system drive
                        disk_paths_to_try.append((drive, f"drive {drive}"))
        else:
            # Unix-like systems
            disk_paths_to_try.append(('/', "root directory"))
            disk_paths_to_try.append((os.path.abspath(os.curdir), "current directory"))
            disk_paths_to_try.append((os.path.expanduser("~"), "home directory"))
        
        # Try each path with shutil first, then fallback to psutil
        disk_errors = []
        disk_found = False
        
        # First attempt: Try with shutil (standard library)
        for disk_path, path_name in disk_paths_to_try:
            try:
                logger.info(f"Trying to get disk metrics with shutil from {path_name}: {disk_path}")
                disk = shutil.disk_usage(disk_path)
                
                # If we get here, the disk metrics were successful
                metrics['disk_percent'] = round((disk.used / disk.total) * 100, 1)
                metrics['disk_used'] = disk.used
                metrics['disk_total'] = disk.total
                metrics['disk_free'] = disk.free
                
                # Add human-readable versions for easier template access
                metrics['disk_used_gb'] = round(disk.used / (1024**3), 2)
                metrics['disk_total_gb'] = round(disk.total / (1024**3), 2)
                metrics['disk_free_gb'] = round(disk.free / (1024**3), 2)
                
                logger.info(f"Successfully got disk metrics from {path_name} using shutil: {metrics['disk_percent']}%, "
                            f"Used: {metrics['disk_used_gb']} GB, Total: {metrics['disk_total_gb']} GB")
                
                disk_found = True
                break
                
            except Exception as e:
                error_msg = repr(e)
                logger.warning(f"Failed to get disk usage with shutil from {path_name}: {error_msg}")
                disk_errors.append(f"{path_name} shutil error: {error_msg}")
                continue
        
        # Second attempt: Try with psutil if shutil failed
        if not disk_found:
            logger.info("Shutil failed, trying psutil for disk metrics")
            for disk_path, path_name in disk_paths_to_try:
                try:
                    logger.info(f"Trying to get disk metrics with psutil from {path_name}: {disk_path}")
                    disk = psutil.disk_usage(disk_path)
                    
                    # If we get here, the disk metrics were successful
                    metrics['disk_percent'] = disk.percent
                    metrics['disk_used'] = disk.used
                    metrics['disk_total'] = disk.total
                    metrics['disk_free'] = disk.free
                    
                    # Add human-readable versions for easier template access
                    metrics['disk_used_gb'] = round(disk.used / (1024**3), 2)
                    metrics['disk_total_gb'] = round(disk.total / (1024**3), 2)
                    metrics['disk_free_gb'] = round(disk.free / (1024**3), 2)
                    
                    logger.info(f"Successfully got disk metrics from {path_name} using psutil: {metrics['disk_percent']}%, "
                                f"Used: {metrics['disk_used_gb']} GB, Total: {metrics['disk_total_gb']} GB")
                    
                    disk_found = True
                    break
                    
                except Exception as e:
                    error_msg = repr(e)
                    logger.warning(f"Failed to get disk usage with psutil from {path_name}: {error_msg}")
                    disk_errors.append(f"{path_name} psutil error: {error_msg}")
                    continue
        
        # If we've tried all paths and approaches, and none worked
        if not disk_found:
            error_detail = " | ".join(disk_errors)
            logger.error(f"All disk metric approaches failed: {error_detail}")
            metrics['disk_error'] = "Could not access any disk paths for metrics"
            # Set default values so we don't cause KeyErrors elsewhere
            metrics['disk_percent'] = 0
            metrics['disk_used'] = 0
            metrics['disk_total'] = 0
            metrics['disk_free'] = 0
            metrics['disk_used_gb'] = 0
            metrics['disk_total_gb'] = 0
            metrics['disk_free_gb'] = 0
            
    except Exception as e:
        logger.error(f"Error getting disk metrics: {repr(e)}")
        # Set default values so we don't cause KeyErrors elsewhere
        metrics['disk_error'] = "Failed to retrieve disk metrics"
        metrics['disk_percent'] = 0
        metrics['disk_used'] = 0
        metrics['disk_total'] = 0 
        metrics['disk_free'] = 0
        metrics['disk_used_gb'] = 0
        metrics['disk_total_gb'] = 0
        metrics['disk_free_gb'] = 0
    
    return metrics

def get_task_history(job_id, history_dir=None):
    """
    Get the execution history for a task.
    
    Args:
        job_id: The job ID
        history_dir: Directory with task execution history (optional)
        
    Returns:
        List of execution histories
    """
    history = []
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        # Use provided history_dir or get from current_app config
        if history_dir is None:
            from flask import current_app
            if current_app:
                history_dir = current_app.config['TASK_HISTORY_DIR']
            else:
                logger.error("No history directory provided and no Flask app context available")
                return history
        
        history_dir_path = Path(history_dir)
        if not history_dir_path.exists():
            logger.warning(f"History directory does not exist: {history_dir_path}")
            return history
            
        for file in history_dir_path.glob(f"{job_id}_*.json"):
            try:
                with open(file, 'r') as f:
                    history.append(json.load(f))
            except Exception as e:
                logger.error(f"Error reading history file {file}: {str(e)}")
                
        # Sort by timestamp
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    except Exception as e:
        logger.error(f"Error getting task history: {str(e)}")
        
    return history

def load_script(script_path):
    """
    Dynamically load a script.
    For Python scripts, loads the module and returns it.
    For other script types (PowerShell, Batch), creates a callable wrapper.
    
    Args:
        script_path: Path to the script
        
    Returns:
        For Python scripts: The loaded module object
        For other scripts: A wrapper object with a 'main' function that executes the script
    """
    logger = logging.getLogger("EzTaskRunner")
    
    # Determine script type based on file extension
    script_type = Path(script_path).suffix.lower()
    
    try:
        if script_type == '.py':
            # Python script - load as module
            spec = importlib.util.spec_from_file_location("dynamic_script", script_path)
            if spec is None:
                raise ImportError(f"Could not load spec for {script_path}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["dynamic_script"] = module
            spec.loader.exec_module(module)
            return module
        else:
            # PowerShell or Batch script - create a wrapper
            class ScriptWrapper:
                @staticmethod
                def main(*args, **kwargs):
                    """
                    Execute the script as a subprocess and return its output.
                    This mimics the behavior of calling module.main() for Python scripts.
                    """
                    # We'll use the run_script function for actual execution
                    result = run_script(script_path, **kwargs)
                    # Return the output or error message
                    if result['success']:
                        return result['output']
                    else:
                        return f"Error executing script: {result['error']}"
            
            return ScriptWrapper()
    except Exception as e:
        logger.error(f"Error loading script {script_path}: {str(e)}")
        raise

def run_script(script_path, job_id=None, history_dir=None, max_runtime_minutes=60, buffer_metrics=None, **kwargs):
    """
    Run a script and capture its output.
    Supports Python (.py), PowerShell (.ps1), and Batch (.bat, .cmd) files.
    
    Args:
        script_path: Path to the script
        job_id: Optional job ID for the task
        history_dir: Directory to store task execution history
        max_runtime_minutes: Maximum allowed runtime in minutes (default: 60)
        buffer_metrics: Optional metrics from the buffer period
        **kwargs: Additional arguments to pass to the script's main function (Python only)
        
    Returns:
        A dictionary containing the execution result and output
    """
    logger = logging.getLogger("EzTaskRunner")
    start_time = time.time()
    result = {
        'success': False,
        'output': '',
        'error': '',
        'execution_time': 0,
        'timestamp': datetime.now().isoformat(),
        'process_id': None
    }
    
    # Add buffer metrics if provided
    if buffer_metrics:
        result['buffer_resource_check'] = buffer_metrics
    
    try:
        logger.info(f"Running script {script_path} with job_id {job_id}, max runtime: {max_runtime_minutes} minutes")
        
        # Determine script type based on file extension
        script_type = Path(script_path).suffix.lower()
        
        # Prepare command based on script type
        if script_type == '.py':
            # Python script
            cmd = [sys.executable, script_path]
            # Convert kwargs to command line arguments if needed
            if kwargs:
                cmd.append('--kwargs')
                cmd.append(json.dumps(kwargs))
        elif script_type == '.ps1':
            # PowerShell script
            cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', script_path]
            # PowerShell doesn't support kwargs the same way, so we ignore them
            if kwargs:
                logger.warning(f"Keyword arguments are not supported for PowerShell scripts. Ignoring: {kwargs}")
        elif script_type in ['.bat', '.cmd']:
            # Batch script
            cmd = [script_path]
            # Batch doesn't support kwargs the same way, so we ignore them
            if kwargs:
                logger.warning(f"Keyword arguments are not supported for Batch scripts. Ignoring: {kwargs}")
        else:
            raise ValueError(f"Unsupported script type: {script_type}")
        
        # Create subprocess with process isolation
        # Use BELOW_NORMAL_PRIORITY_CLASS on Windows or nice on Unix to lower process priority
        process_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True,
            'bufsize': 1,  # Line buffered for better real-time logging
            'close_fds': True  # Ensure file descriptors aren't shared with parent process
        }
        
        # For Windows batch scripts, we need to use shell=True
        if script_type in ['.bat', '.cmd'] and platform.system() == "Windows":
            process_kwargs['shell'] = True
        
        # Set process priority based on platform
        if platform.system() == "Windows":
            # BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            process_kwargs['creationflags'] = 0x00004000
        else:
            # On Unix-like systems, use preexec_fn with nice
            def lower_priority():
                try:
                    os.nice(10)  # Lower priority (higher nice value)
                except Exception:
                    pass  # Ignore if we can't set priority
            
            process_kwargs['preexec_fn'] = lower_priority
        
        # Run the subprocess with modified priority
        process = subprocess.Popen(cmd, **process_kwargs)
        
        # Store the process ID
        result['process_id'] = process.pid
        logger.info(f"Started process ID {process.pid} for task {job_id}")
        
        # Wait for the process to complete (with timeout based on max_runtime_minutes)
        try:
            # Convert minutes to seconds for the timeout
            timeout_seconds = max_runtime_minutes * 60
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            # Store the output and error
            result['output'] = stdout
            
            # Check if the process completed successfully
            if process.returncode == 0:
                result['success'] = True
                # Log successful completion
                logger.info(f"Script {script_path} completed successfully with exit code 0")
                # Even if there's stderr output with returncode 0, we consider it successful
                # but we'll include the stderr in the output for reference
                if stderr and stderr.strip():
                    result['output'] += f"\n\nSTDERR Output:\n{stderr}"
            else:
                result['error'] = stderr or f"Process exited with code {process.returncode}"
                logger.error(f"Script {script_path} exited with code {process.returncode}")
        except subprocess.TimeoutExpired:
            # Kill the process if it times out
            process.kill()
            stdout, stderr = process.communicate()
            result['error'] = f"Process timed out after {max_runtime_minutes} minutes and was terminated"
            logger.error(f"Script {script_path} timed out after {max_runtime_minutes} minutes and was terminated")
            
    except Exception as e:
        error_msg = str(e)
        stack_trace = traceback.format_exc()
        logger.error(f"Error running script {script_path}: {error_msg}\n{stack_trace}")
        result['error'] = f"{error_msg}\n{stack_trace}"
    
    # Calculate execution time
    execution_time = time.time() - start_time
    result['execution_time'] = execution_time
    
    # Store result in task history if directory is provided
    if history_dir:
        try:
            os.makedirs(history_dir, exist_ok=True)
            history_file = Path(history_dir) / f"{job_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            with open(history_file, 'w') as f:
                json.dump(result, f, indent=2)
                logger.info(f"Task history saved to {history_file}")
        except Exception as e:
            logger.error(f"Error saving task history: {str(e)}")
    
    # Log the final result for debugging
    if result['success']:
        logger.info(f"Task {job_id} execution completed successfully in {execution_time:.2f} seconds")
    else:
        logger.error(f"Task {job_id} execution failed in {execution_time:.2f} seconds with error: {result.get('error', 'Unknown error')[:200]}...")
    
    return result

def kill_task(process_id):
    """
    Kill a running task process.
    
    Args:
        process_id: The process ID to kill
        
    Returns:
        dict: Results of the kill operation
    """
    logger = logging.getLogger("EzTaskRunner")
    result = {
        "success": False,
        "message": "",
        "error": None
    }
    
    if not process_id:
        result["error"] = "No process ID provided"
        return result
    
    try:
        # Convert to int if it's a string
        if isinstance(process_id, str) and process_id.isdigit():
            process_id = int(process_id)
            
        # Check if process exists
        if not psutil.pid_exists(process_id):
            result["error"] = f"Process with ID {process_id} not found"
            return result
            
        # Get the process and terminate it and all its children
        process = psutil.Process(process_id)
        process_name = process.name()
        
        # Kill child processes first
        children = process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except:
                pass
                
        # Wait for children to terminate
        _, still_alive = psutil.wait_procs(children, timeout=3)
        
        # Kill any remaining children
        for child in still_alive:
            try:
                child.kill()
            except:
                pass
        
        # Now kill the parent process
        process.terminate()
        
        # Wait for up to 3 seconds
        process.wait(timeout=3)
        
        # If still running, force kill
        if process.is_running():
            process.kill()
            
        result["success"] = True
        result["message"] = f"Successfully terminated process {process_id} ({process_name})"
        logger.info(f"Task process terminated: {process_id} ({process_name})")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error killing process {process_id}: {error_msg}")
        result["error"] = error_msg
    
    return result

def purge_logs(log_dir=None, days_to_keep=30, keep_files=None):
    """
    Delete log files older than the specified number of days.
    
    Args:
        log_dir: Directory containing log files (optional)
        days_to_keep: Number of days to keep logs (default: 30)
        keep_files: List of filenames to always keep (default: None)
    
    Returns:
        dict: Results of the purge operation
    """
    logger = logging.getLogger("EzTaskRunner")
    result = {
        "success": True,
        "purged_files": [],
        "error": None
    }
    
    try:
        # Use provided log_dir or get from current_app config
        if log_dir is None:
            from flask import current_app
            if current_app:
                log_dir = current_app.config['LOG_DIR']
            else:
                error_msg = "No log directory provided and no Flask app context available"
                logger.error(error_msg)
                result["success"] = False
                result["error"] = error_msg
                return result
        
        # Set default for files to always keep
        if keep_files is None:
            keep_files = ["eztaskrunner.log", "tasks.log", "errors.log"]
        
        log_dir_path = Path(log_dir)
        if not log_dir_path.exists():
            error_msg = f"Log directory does not exist: {log_dir_path}"
            logger.error(error_msg)
            result["success"] = False
            result["error"] = error_msg
            return result
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Process all log files
        for file_path in log_dir_path.glob("*.log"):
            if file_path.name in keep_files:
                logger.info(f"Skipping purge for protected file: {file_path.name}")
                continue
                
            # Check file modification time
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff_date:
                try:
                    file_path.unlink()
                    logger.info(f"Purged old log file: {file_path.name}")
                    result["purged_files"].append(file_path.name)
                except Exception as e:
                    logger.error(f"Error deleting log file {file_path.name}: {str(e)}")
        
        logger.info(f"Log purge completed. Removed {len(result['purged_files'])} files.")
    except Exception as e:
        error_msg = f"Error purging logs: {str(e)}"
        logger.error(error_msg)
        result["success"] = False
        result["error"] = error_msg
    
    return result 