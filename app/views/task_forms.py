"""
Task form views for EzTaskRunner.
Renders forms for task creation and editing.
"""
from flask import render_template, current_app

def render_add_task_form():
    """
    Render the form for adding a new task.
    
    Returns:
        Rendered template with form
    """
    return render_template(
        'tasks/add_task.html',
        title="Add Task"
    )

def render_edit_task_form(task):
    """
    Render the form for editing an existing task.
    
    Args:
        task: The task data dictionary
        
    Returns:
        Rendered template with form and task data
    """
    return render_template(
        'tasks/edit_task.html',
        task=task,
        title=f"Edit Task: {task.get('task_name', '')}"
    ) 