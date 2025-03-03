"""
History views for EzTaskRunner.
Renders task execution history.
"""
from flask import render_template, current_app

def render_task_history(task, history):
    """
    Render the task execution history.
    
    Args:
        task: The task data dictionary
        history: List of execution history entries
        
    Returns:
        Rendered template with task and history data
    """
    return render_template(
        'tasks/history.html',
        task=task,
        history=history,
        title=f"History: {task.get('task_name', '')}"
    ) 