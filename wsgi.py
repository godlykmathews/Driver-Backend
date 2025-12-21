#!/usr/bin/env python3
"""
WSGI entry point for PythonAnywhere deployment
This file converts the FastAPI ASGI app to WSGI for PythonAnywhere
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

# Set the DJANGO_SETTINGS_MODULE if needed (not used here but good practice)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

# Import the ASGI app
from app.main import app

# Convert ASGI to WSGI using a2wsgi
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
    print("✅ Using a2wsgi for ASGI to WSGI conversion")
except ImportError:
    print("❌ a2wsgi not installed. Please install it with: pip install a2wsgi")
    # Fallback - this won't work but will show the error
    application = None
