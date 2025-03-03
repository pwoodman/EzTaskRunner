#!/usr/bin/env python
"""
Debug script for the settings route
"""
import sys
import logging
from app import create_app
from flask import current_app

# Configure logging to see detailed information
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("debug")

def debug_settings_route():
    """Debug the settings route"""
    try:
        logger.info("Creating test app...")
        app = create_app()
        
        # Manually simulate a request to the settings route
        with app.test_request_context('/settings'):
            from app.routes.settings import settings
            
            # Print local and global variables
            logger.info("Inspecting the settings function...")
            logger.info(f"Function name: {settings.__name__}")
            logger.info(f"Function globals: {list(settings.__globals__.keys())}")
            
            # Try to execute the route function
            logger.info("Attempting to execute the settings function...")
            try:
                result = settings()
                logger.info(f"Result: {result}")
            except Exception as e:
                logger.error(f"Error executing settings function: {e}", exc_info=True)
            
            # Check the app configuration
            logger.info("Checking app configuration...")
            for key in sorted(current_app.config.keys()):
                logger.info(f"Config: {key} = {current_app.config[key]}")
        
        logger.info("Debug complete.")
    except Exception as e:
        logger.error(f"Error during debug: {e}", exc_info=True)

if __name__ == "__main__":
    debug_settings_route() 