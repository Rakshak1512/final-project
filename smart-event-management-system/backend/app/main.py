import logging
import os

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import (
    admin_routes,
    analytics_routes,
    auth_routes,
    certificate_routes,
    chatbot_routes,
    event_routes,
    feedback_routes,
    notification_routes,
    registration_routes,
    result_routes,
    search_routes,
    user_routes,
    volunteer_routes,
    websocket_routes,
)
from app.core.config import settings
from app.core.firebase import init_firebase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])

app = FastAPI(
    title=settings.APP_NAME,
    description="REST API for the Smart Event Management System (Firebase Edition)",
    version="1.0.0",
)

app.add_middleware(GZipMiddleware, minimum_size=800)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.trycloudflare\.com|https://.*\.loca\.lt",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def vercel_path_rewrite_middleware(request: Request, call_next):
    path = request.scope.get("path", "")
    route_param = request.query_params.get("__route")

    target_path = None
    if route_param:
        target_path = route_param
    elif request.headers.get("x-matched-path") and not request.headers.get("x-matched-path", "").startswith("/api/index.py"):
        target_path = request.headers.get("x-matched-path").split("?", 1)[0]
    elif request.headers.get("x-forwarded-uri") and not request.headers.get("x-forwarded-uri", "").startswith("/api/index.py"):
        target_path = request.headers.get("x-forwarded-uri").split("?", 1)[0]
    elif path.startswith("/api/index.py/"):
        target_path = path[len("/api/index.py"):]
    elif path == "/api/index.py":
        target_path = "/api"

    if target_path:
        if not target_path.startswith("/"):
            target_path = "/" + target_path
        while "//" in target_path:
            target_path = target_path.replace("//", "/")
        request.scope["path"] = target_path

    return await call_next(request)

try:
    os.makedirs(settings.upload_dir_abs, exist_ok=True)
    for sub in ("profile_pictures", "event_posters", "certificates", "qrcodes"):
        os.makedirs(os.path.join(settings.upload_dir_abs, sub), exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir_abs), name="uploads")
except Exception as _fs_err:
    logger.warning("Could not mount local /uploads directory (serverless read-only mode): %s", _fs_err)


@app.on_event("startup")
def on_startup():
    try:
        init_firebase()
        logger.info("[FIREBASE] Firebase Firestore initialized and connected successfully.")
    except Exception as e:
        logger.error(f"[FIREBASE] Error initializing Firebase Firestore: {e}")

    if settings.SEED_TEST_USERS:
        try:
            from app.services.seed_service import seed_test_users
            seed_test_users()
        except Exception as e:
            logger.error(f"[AUTH] Error seeding test users: {e}")

    # Safe email configuration validation without exposing credentials or keys
    smtp_loaded = settings.is_smtp_configured
    sender_addr = settings.SMTP_FROM_EMAIL or settings.SMTP_USER or "noreply@eventsphere.edu"
    pass_len = len(settings.SMTP_PASSWORD) if settings.SMTP_PASSWORD else 0
    valid_len = (pass_len == 16)
    logger.info(
        f"[EMAIL] Provider: Gmail SMTP | Status: {'CONFIGURED' if smtp_loaded else 'CREDENTIALS NEEDED'} "
        f"| Host: {settings.SMTP_HOST}:{settings.SMTP_PORT} (TLS: {settings.SMTP_USE_TLS}) | Sender: {sender_addr} "
        f"| App Password Format: {'VALID (16 chars)' if valid_len else f'INVALID LENGTH ({pass_len} chars, expected 16)' if pass_len else 'NOT SET'}"
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": errors})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.get("/api", tags=["Health"])
@app.get("/api/", tags=["Health"])
def api_root():
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "database": "firestore"}


@app.get("/api/health/email", tags=["Health"])
def email_health_check(check_auth: bool = False):
    smtp_configured = settings.is_smtp_configured
    sender_addr = settings.SMTP_FROM_EMAIL or settings.SMTP_USER or "noreply@eventsphere.edu"
    pass_len = len(settings.SMTP_PASSWORD) if settings.SMTP_PASSWORD else 0

    res = {
        "provider": "smtp",
        "status": "configured" if smtp_configured else "credentials_required",
        "sender_email": sender_addr,
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "smtp_use_tls": settings.SMTP_USE_TLS,
        "smtp_configured": smtp_configured,
        "password_length": pass_len,
        "is_valid_app_password_format": pass_len == 16,
    }
    if check_auth:
        from app.services.email_service import test_smtp_connection
        auth_ok, auth_detail = test_smtp_connection()
        res["auth_tested"] = True
        res["auth_success"] = auth_ok
        res["auth_message"] = auth_detail
    return res


app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(event_routes.router)
app.include_router(registration_routes.router)
app.include_router(certificate_routes.router)
app.include_router(notification_routes.router)
app.include_router(analytics_routes.router)
app.include_router(chatbot_routes.router)
app.include_router(feedback_routes.router)
app.include_router(volunteer_routes.router)
app.include_router(admin_routes.router)
app.include_router(admin_routes.faculty_task_router)
app.include_router(admin_routes.faculty_approval_router)
app.include_router(admin_routes.reports_root_router)
app.include_router(result_routes.router)
app.include_router(search_routes.router)
app.include_router(websocket_routes.router)

# Mount static frontend assets and provide SPA fallback routing
_dist_search_paths = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend", "dist"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "smart-event-management-system", "frontend", "dist"),
    os.path.abspath("smart-event-management-system/frontend/dist"),
    "/var/task/smart-event-management-system/frontend/dist",
]
_frontend_dist = None
for _dp in _dist_search_paths:
    if os.path.exists(_dp) and os.path.exists(os.path.join(_dp, "index.html")):
        _frontend_dist = os.path.abspath(_dp)
        break

if _frontend_dist:
    _assets_dir = os.path.join(_frontend_dist, "assets")
    if os.path.exists(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        index_html = os.path.join(_frontend_dist, "index.html")
        return FileResponse(index_html)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_frontend(request: Request, full_path: str):
        if full_path.startswith(("api/", "docs", "openapi.json", "uploads/")):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = os.path.join(_frontend_dist, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        index_html = os.path.join(_frontend_dist, "index.html")
        if os.path.isfile(index_html):
            return FileResponse(index_html)
        raise HTTPException(status_code=404, detail="Not Found")
else:
    @app.get("/", tags=["Health"])
    def root():
        return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}
