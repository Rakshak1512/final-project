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

from app.main import app as fastapi_app


class VercelPathMiddleware:
    """
    Middleware that recovers the original request path on Vercel deployments.
    When Vercel rewrites /api/(.*) -> /api/index.py, the ASGI path becomes '/api/index.py'
    while the actual client URL is passed in headers like 'x-matched-path' or 'x-now-route-matches'.
    """
    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            matched = headers.get(b"x-matched-path")
            if matched:
                path_str = matched.decode("utf-8").split("?", 1)[0]
                scope["path"] = path_str
                scope["raw_path"] = path_str.encode("utf-8")
        await self.inner_app(scope, receive, send)


app = VercelPathMiddleware(fastapi_app)

try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except Exception:
    handler = app
