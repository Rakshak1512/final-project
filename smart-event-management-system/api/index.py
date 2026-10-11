"""
Vercel Serverless Function entry point for EventSphere FastAPI backend.
Exports ASGI 'app' (for Vercel native Python ASGI runtime)
and Mangum 'handler' (for AWS Lambda / WSGI/ASGI adapters).
"""
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_possible_backend_paths = [
    os.path.join(_current_dir, "..", "backend"),
    os.path.join(_current_dir, "backend"),
    os.path.join(_current_dir, "..", "smart-event-management-system", "backend"),
]
for _p in _possible_backend_paths:
    _abs_p = os.path.abspath(_p)
    if os.path.exists(_abs_p) and _abs_p not in sys.path:
        sys.path.insert(0, _abs_p)
        break

from app.main import app

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except Exception:
    handler = app
