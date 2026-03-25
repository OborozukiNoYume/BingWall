import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api.errors import ApiError
from app.api.errors import api_error_exception_handler
from app.api.errors import request_validation_exception_handler
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import bind_trace_id, configure_logging, reset_trace_id
from app.web import get_assets_dir
from app.web import get_admin_assets_dir
from app.web import router as web_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="BingWall API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router)
    app.include_router(web_router)
    app.add_exception_handler(ApiError, api_error_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.mount("/assets", StaticFiles(directory=get_assets_dir()), name="assets")
    app.mount("/admin-assets", StaticFiles(directory=get_admin_assets_dir()), name="admin-assets")
    app.mount(
        "/images",
        StaticFiles(directory=settings.storage_public_dir, check_dir=False),
        name="images",
    )

    @app.middleware("http")
    async def trace_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id", str(uuid4()))
        token = bind_trace_id(trace_id)
        request.state.trace_id = trace_id
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logging.getLogger("app.access").info(
                "Request completed method=%s path=%s status_code=%s duration_ms=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        finally:
            reset_trace_id(token)
        response.headers["X-Trace-Id"] = trace_id
        return response

    logger = logging.getLogger(__name__)
    logger.info("Application configured for %s:%s.", settings.app_host, settings.app_port)
    return app
