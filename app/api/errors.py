from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from pydantic import ValidationError


class ApiError(Exception):
    def __init__(self, *, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "-")


def build_success_response(
    *,
    request: Request,
    data: Any,
    pagination: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "message": "ok",
        "data": data,
        "trace_id": get_trace_id(request),
        "pagination": pagination,
    }


def build_error_response(
    *,
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "error_code": error_code,
            "data": None,
            "trace_id": get_trace_id(request),
        },
    )


def request_validation_exception_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, (RequestValidationError, ValidationError)):
        raise TypeError("request_validation_exception_handler received unexpected exception type")
    errors = exc.errors()
    message = "参数错误"
    if errors:
        location = ".".join(str(part) for part in errors[0].get("loc", ()) if part != "query")
        detail = errors[0].get("msg", "invalid request")
        if location:
            message = f"参数错误: {location} {detail}"
        else:
            message = f"参数错误: {detail}"
    return build_error_response(
        request=request,
        status_code=422,
        error_code="COMMON_INVALID_ARGUMENT",
        message=message,
    )


def api_error_exception_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, ApiError):
        raise TypeError("api_error_exception_handler received unexpected exception type")
    return build_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
    )
