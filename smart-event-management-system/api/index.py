"""
Vercel Serverless Function entry point when root directory is set to smart-event-management-system.
"""
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_path = os.path.abspath(os.path.join(_current_dir, "..", "backend"))
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from app.main import app

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except Exception:
    handler = app
