#!/usr/bin/env python
"""
EzTaskRunner application runner script.

This script starts the Flask web server for the EzTaskRunner application.
"""
import os
import argparse
import logging
from pathlib import Path
from app import app

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run the EzTaskRunner application')
    parser.add_argument('--host', default='127.0.0.1', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    return parser.parse_args()

def ensure_directories_exist():
    """Ensure all required directories exist."""
    directories = [
        'scripts',
        'logs',
        'task_history',
        'tasks',
        'data'  # Add a data directory for scripts to use
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Ensured directory exists: {directory}")

if __name__ == '__main__':
    # Ensure directories exist
    ensure_directories_exist()
    
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    logger = logging.getLogger("EzTaskRunner")
    logger.info(f"Starting EzTaskRunner on {args.host}:{args.port} (debug={args.debug})")
    
    # Run the application
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    ) 