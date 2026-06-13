"""
LifeLink API — Vercel Serverless Entry Point
Wraps the Flask backend as a Vercel-compatible WSGI application.
"""
import os
import sys

# Add the backend directory to the Python path so imports work
# Checks os.getcwd() first (Vercel project root at runtime) and falls back to __file__ relative path
ROOT_DIR = os.getcwd()
BACKEND_DIR = os.path.join(ROOT_DIR, 'backend')
if not os.path.exists(os.path.join(BACKEND_DIR, 'app.py')):
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BACKEND_DIR = os.path.join(ROOT_DIR, 'backend')

sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, ROOT_DIR)

# Set environment variable so database.py knows we're on Vercel
os.environ['VERCEL'] = '1'

# Import the Flask app from the backend
try:
    from backend.app import app
except ImportError:
    # pyrefly: ignore [missing-import]
    from app import app

# Vercel expects the WSGI app to be exposed as `app`
# The variable name must match the filename: index.py → `app`
