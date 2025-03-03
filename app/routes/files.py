"""
Files routes for EzTaskRunner.
Handles file browsing and script selection.
"""
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app

# Create blueprint
files_bp = Blueprint('files', __name__, url_prefix='')

@files_bp.route("/browse_files")
def browse_files():
    """
    Return a JSON list of directories and script files within the scripts directory.
    Supports Python (.py), PowerShell (.ps1), and Batch (.bat, .cmd) files.
    This endpoint is used by the file browser modal.
    """
    logger = logging.getLogger("EzTaskRunner")
    
    try:
        scripts_dir = current_app.config['SCRIPTS_DIR'].resolve()
        current_dir_param = request.args.get("dir", "")
        
        if current_dir_param:
            target_dir = (scripts_dir / current_dir_param).resolve()
            try:
                # Ensure we don't browse outside the scripts directory (directory traversal prevention)
                target_dir.relative_to(scripts_dir)
            except ValueError:
                logger.warning(f"Attempted directory traversal: {current_dir_param}")
                return jsonify({"error": "Cannot browse outside the scripts directory"}), 400
            current_path = target_dir
        else:
            current_path = scripts_dir

        files, dirs = [], []
        
        # Add parent directory option if we're in a subdirectory
        if current_path != scripts_dir:
            parent_dir = str(current_path.relative_to(scripts_dir).parent)
            dirs.append({"name": "..", "path": parent_dir if parent_dir != "." else ""})

        # Valid script file extensions
        valid_extensions = ['.py', '.ps1', '.bat', '.cmd']
        
        # List directories and script files
        for item in current_path.iterdir():
            rel_path = str(item.relative_to(scripts_dir))
            if item.is_dir():
                dirs.append({"name": item.name, "path": rel_path})
            elif item.suffix.lower() in valid_extensions:
                # Add script type info
                script_type = item.suffix.lower()[1:]  # Remove the leading dot
                if script_type in ['bat', 'cmd']:
                    script_type = 'batch'
                
                files.append({
                    "name": item.name, 
                    "path": rel_path,
                    "type": script_type
                })

        return jsonify({
            "current_dir": str(current_path.relative_to(scripts_dir)),
            "directories": sorted(dirs, key=lambda x: x["name"]),
            "files": sorted(files, key=lambda x: x["name"])
        })
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error browsing files: {error_msg}")
        return jsonify({"error": error_msg}), 400 