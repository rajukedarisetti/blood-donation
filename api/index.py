"""
LifeLink API — Vercel Serverless Entry Point
Wraps the Flask backend as a Vercel-compatible WSGI application.
"""
import os
import sys

# Add the backend directory to the Python path so imports work
BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, BACKEND_DIR)

# Set environment variable so database.py knows we're on Vercel
os.environ['VERCEL'] = '1'

# Import the Flask app from the backend
from app import app

# Vercel expects the WSGI app to be exposed as `app`
# The variable name must match the filename: index.py → `app`
