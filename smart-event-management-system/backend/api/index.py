"""
Vercel Serverless Function entry point for EventSphere FastAPI backend
when deployed with Root Directory set to 'smart-event-management-system/backend'.
Exports ASGI 'app' (for Vercel native Python ASGI runtime)
and Mangum 'handler' (for AWS Lambda / ASGI adapters).
"""
import os
import sys

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.main import app

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except Exception:
    handler = app
