import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import bind_trace_id, configure_logging, reset_trace_id


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

    @app.middleware("http")
    async def trace_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id", str(uuid4()))
        token = bind_trace_id(trace_id)
        try:
            response = await call_next(request)
        finally:
            reset_trace_id(token)
        response.headers["X-Trace-Id"] = trace_id
        return response

    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "service": "bingwall-api",
            "status": "ok",
            "health_url": "/api/health/live",
        }

    logger = logging.getLogger(__name__)
    logger.info("Application configured for %s:%s.", settings.app_host, settings.app_port)
    return app
