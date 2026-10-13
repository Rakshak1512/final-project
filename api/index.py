"""
Vercel Serverless Function entry point for EventSphere FastAPI backend.
Exports ASGI 'app' (for Vercel native Python ASGI runtime)
and Mangum 'handler' (for AWS Lambda / WSGI/ASGI adapters).
"""
import os
import sys

_current_dir = os.path.dirname(os.path.abspath(__file__))
_possible_backend_paths = [
    os.path.join(_current_dir, "..", "smart-event-management-system", "backend"),
    os.path.join(_current_dir, "..", "backend"),
    os.path.join(_current_dir, "backend"),
]
for _p in _possible_backend_paths:
    _abs_p = os.path.abspath(_p)
    if os.path.exists(_abs_p) and _abs_p not in sys.path:
        sys.path.insert(0, _abs_p)
        break

from app.main import app

try:
    from mangum import Mangum
    _mangum_handler = Mangum(app, lifespan="off")

    def handler(event, context):
        if isinstance(event, dict):
            qs = event.get("queryStringParameters") or {}
            route = qs.get("__route")
            if not route:
                headers = event.get("headers") or {}
                matched = headers.get("x-matched-path") or headers.get("x-forwarded-uri") or headers.get("x-vercel-matched-path")
                if matched and not matched.startswith("/api/index.py"):
                    route = matched.split("?", 1)[0]
            if route:
                if not route.startswith("/"):
                    route = "/" + route
                event["path"] = route
                event["rawPath"] = route
                if "requestContext" in event and isinstance(event["requestContext"], dict):
                    if "http" in event["requestContext"] and isinstance(event["requestContext"]["http"], dict):
                        event["requestContext"]["http"]["path"] = route
            elif event.get("path") == "/api/index.py" or event.get("rawPath") == "/api/index.py":
                event["path"] = "/api"
                event["rawPath"] = "/api"
                if "requestContext" in event and isinstance(event["requestContext"], dict):
                    if "http" in event["requestContext"] and isinstance(event["requestContext"]["http"], dict):
                        event["requestContext"]["http"]["path"] = "/api"
        return _mangum_handler(event, context)
except Exception:
    handler = app
