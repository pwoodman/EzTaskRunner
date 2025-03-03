"""
Dashboard views for EzTaskRunner.
Renders the main dashboard with task list.
"""
from flask import render_template, current_app, request

from app.task_manager import get_all_tasks

def render_dashboard():
    """
    Render the main dashboard with task list.
    
    Returns:
        Rendered template with task data
    """
    # Get search query if any
    search_query = request.args.get('search', '').strip().lower()
    
    # Get all tasks
    tasks = get_all_tasks()
    
    # Filter tasks if search query exists
    if search_query:
        filtered_tasks = []
        for task in tasks:
            # Check if search term exists in task name, description, or script path
            task_name = task.get('task_name', '').lower()
            description = task.get('description', '').lower()
            script_path = task.get('script_path', '').lower()
            
            if (search_query in task_name or 
                search_query in description or 
                search_query in script_path):
                filtered_tasks.append(task)
        tasks = filtered_tasks
    
    # Get scheduler
    scheduler = current_app.config.get('SCHEDULER')
    
    # Add job info to tasks
    for task in tasks:
        job_id = task.get('job_id')
        if scheduler and job_id:
            job = scheduler.get_job(job_id)
            if job:
                task['next_run'] = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "Not scheduled"
            else:
                task['next_run'] = "Not scheduled"
    
    return render_template(
        'dashboard/index.html',
        tasks=tasks,
        title="Task Dashboard"
    ) 