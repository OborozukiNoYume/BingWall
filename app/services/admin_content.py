from __future__ import annotations

from datetime import UTC
from datetime import datetime
import json
import math
from sqlite3 import Row
from typing import Any
from typing import cast

from app.api.errors import ApiError
from app.repositories.admin_content_repository import AdminContentRepository
from app.schemas.admin_auth import AdminSessionContext
from app.schemas.admin_content import AdminAuditLogListData
from app.schemas.admin_content import AdminAuditLogListQuery
from app.schemas.admin_content import AdminAuditLogSummary
from app.schemas.admin_content import ContentStatus
from app.schemas.admin_content import ImageStatus
from app.schemas.admin_content import AdminWallpaperDetailData
from app.schemas.admin_content import AdminWallpaperListData
from app.schemas.admin_content import AdminWallpaperListQuery
from app.schemas.admin_content import AdminWallpaperStatusUpdateData
from app.schemas.admin_content import AdminWallpaperStatusUpdateRequest
from app.schemas.admin_content import AdminWallpaperSummary
from app.schemas.common import Pagination
from app.services.admin_auth import build_request_source

ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"enabled", "deleted"},
    "enabled": {"disabled", "deleted"},
    "disabled": {"enabled", "deleted"},
    "deleted": set(),
}


class AdminContentService:
    def __init__(self, repository: AdminContentRepository, *, session_secret: str) -> None:
        self.repository = repository
        self.session_secret = session_secret

    def list_wallpapers(
        self, *, query: AdminWallpaperListQuery
    ) -> tuple[AdminWallpaperListData, Pagination]:
        rows, total = self.repository.list_wallpapers(query=query)
        items = [self._build_wallpaper_summary(row) for row in rows]
        total_pages = math.ceil(total / query.page_size) if total else 0
        pagination = Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
        )
        return AdminWallpaperListData(items=items), pagination

    def get_wallpaper_detail(self, *, wallpaper_id: int) -> AdminWallpaperDetailData:
        row = self.repository.get_wallpaper_detail(wallpaper_id=wallpaper_id)
        if row is None:
            raise ApiError(
                status_code=404,
                error_code="CONTENT_WALLPAPER_NOT_FOUND",
                message="壁纸不存在",
            )

        recent_logs = self.repository.list_recent_audit_logs_for_target(
            target_type="wallpaper",
            target_id=str(wallpaper_id),
            limit=10,
        )
        relative_path = optional_text(row["relative_path"])
        return AdminWallpaperDetailData(
            id=int(row["id"]),
            title=present_title(row),
            subtitle=optional_text(row["subtitle"]),
            description=optional_text(row["description"]),
            location_text=optional_text(row["location_text"]),
            copyright_text=optional_text(row["copyright_text"]),
            source_type=str(row["source_type"]),
            source_name=str(row["source_name"]),
            source_key=str(row["source_key"]),
            market_code=str(row["market_code"]),
            wallpaper_date=str(row["wallpaper_date"]),
            published_at_utc=optional_text(row["published_at_utc"]),
            publish_start_at_utc=optional_text(row["publish_start_at_utc"]),
            publish_end_at_utc=optional_text(row["publish_end_at_utc"]),
            origin_page_url=optional_text(row["origin_page_url"]),
            origin_image_url=optional_text(row["origin_image_url"]),
            origin_width=optional_int(row["origin_width"]),
            origin_height=optional_int(row["origin_height"]),
            resource_relative_path=relative_path,
            preview_url=build_image_url(relative_path=relative_path),
            resource_type=optional_text(row["resource_type"]),
            storage_backend=optional_text(row["storage_backend"]),
            mime_type=optional_text(row["mime_type"]),
            file_size_bytes=optional_int(row["file_size_bytes"]),
            width=optional_int(row["width"]),
            height=optional_int(row["height"]),
            content_status=parse_content_status(row["content_status"]),
            resource_status=str(row["resource_status"]),
            image_status=parse_image_status(row["image_status"]),
            is_public=bool(row["is_public"]),
            is_downloadable=bool(row["is_downloadable"]),
            failure_reason=optional_text(row["failure_reason"]),
            deleted_at_utc=optional_text(row["deleted_at_utc"]),
            created_at_utc=str(row["created_at_utc"]),
            updated_at_utc=str(row["updated_at_utc"]),
            recent_operations=[self._build_audit_log_summary(log_row) for log_row in recent_logs],
        )

    def update_wallpaper_status(
        self,
        *,
        wallpaper_id: int,
        payload: AdminWallpaperStatusUpdateRequest,
        session: AdminSessionContext,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AdminWallpaperStatusUpdateData:
        row = self.repository.get_wallpaper_for_status_change(wallpaper_id=wallpaper_id)
        if row is None:
            raise ApiError(
                status_code=404,
                error_code="CONTENT_WALLPAPER_NOT_FOUND",
                message="壁纸不存在",
            )

        current_status = parse_content_status(row["content_status"])
        self._validate_status_transition(
            current_status=current_status,
            target_status=payload.target_status,
            resource_status=str(row["resource_status"]),
            image_status=parse_image_status(row["image_status"]),
        )

        changed_at = utc_now_isoformat()
        deleted_at_utc = changed_at if payload.target_status == "deleted" else None
        is_public = payload.target_status == "enabled"
        before_state = {
            "content_status": current_status,
            "is_public": bool(row["is_public"]),
            "resource_status": str(row["resource_status"]),
            "image_status": parse_image_status(row["image_status"]),
            "deleted_at_utc": optional_text(row["deleted_at_utc"]),
        }
        after_state = {
            "content_status": payload.target_status,
            "is_public": is_public,
            "resource_status": str(row["resource_status"]),
            "image_status": parse_image_status(row["image_status"]),
            "deleted_at_utc": deleted_at_utc,
            "operator_reason": payload.operator_reason,
        }

        self.repository.update_wallpaper_status(
            wallpaper_id=wallpaper_id,
            content_status=payload.target_status,
            is_public=is_public,
            deleted_at_utc=deleted_at_utc,
            updated_at_utc=changed_at,
        )
        self.repository.insert_audit_log(
            admin_user_id=session.admin_user_id,
            action_type="wallpaper_status_changed",
            target_type="wallpaper",
            target_id=str(wallpaper_id),
            before_state_json=json.dumps(before_state, ensure_ascii=False),
            after_state_json=json.dumps(after_state, ensure_ascii=False),
            request_source=build_request_source(
                client_ip=client_ip,
                user_agent=user_agent,
                secret=self.session_secret,
            ),
            trace_id=trace_id,
            created_at_utc=changed_at,
        )
        return AdminWallpaperStatusUpdateData(
            wallpaper_id=wallpaper_id,
            previous_status=current_status,
            target_status=payload.target_status,
            is_public=is_public,
            deleted_at_utc=deleted_at_utc,
        )

    def list_audit_logs(
        self, *, query: AdminAuditLogListQuery
    ) -> tuple[AdminAuditLogListData, Pagination]:
        rows, total = self.repository.list_audit_logs(query=query)
        items = [self._build_audit_log_summary(row) for row in rows]
        total_pages = math.ceil(total / query.page_size) if total else 0
        pagination = Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
        )
        return AdminAuditLogListData(items=items), pagination

    def _validate_status_transition(
        self,
        *,
        current_status: str,
        target_status: str,
        resource_status: str,
        image_status: str | None,
    ) -> None:
        allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        if target_status not in allowed_targets:
            raise ApiError(
                status_code=409,
                error_code="CONTENT_INVALID_STATUS_TRANSITION",
                message=f"不允许从 {current_status} 切换到 {target_status}",
            )
        if target_status == "enabled" and (resource_status != "ready" or image_status != "ready"):
            raise ApiError(
                status_code=409,
                error_code="CONTENT_INVALID_STATUS_TRANSITION",
                message="资源未就绪，不能启用内容",
            )

    def _build_wallpaper_summary(self, row: Row) -> AdminWallpaperSummary:
        relative_path = optional_text(row["relative_path"])
        return AdminWallpaperSummary(
            id=int(row["id"]),
            title=present_title(row),
            market_code=str(row["market_code"]),
            wallpaper_date=str(row["wallpaper_date"]),
            source_type=str(row["source_type"]),
            source_name=str(row["source_name"]),
            content_status=parse_content_status(row["content_status"]),
            resource_status=str(row["resource_status"]),
            image_status=parse_image_status(row["image_status"]),
            is_public=bool(row["is_public"]),
            is_downloadable=bool(row["is_downloadable"]),
            preview_url=build_image_url(relative_path=relative_path),
            width=optional_int(row["width"]),
            height=optional_int(row["height"]),
            failure_reason=optional_text(row["failure_reason"]),
            created_at_utc=str(row["created_at_utc"]),
            updated_at_utc=str(row["updated_at_utc"]),
        )

    def _build_audit_log_summary(self, row: Row) -> AdminAuditLogSummary:
        return AdminAuditLogSummary(
            id=int(row["id"]),
            admin_user_id=int(row["admin_user_id"]),
            admin_username=str(row["admin_username"]),
            action_type=str(row["action_type"]),
            target_type=str(row["target_type"]),
            target_id=str(row["target_id"]),
            before_state=parse_optional_json(row["before_state_json"]),
            after_state=parse_optional_json(row["after_state_json"]),
            request_source=optional_text(row["request_source"]),
            trace_id=str(row["trace_id"]),
            created_at_utc=str(row["created_at_utc"]),
        )


def present_title(row: Row) -> str:
    title = optional_text(row["title"])
    if title:
        return title
    copyright_text = optional_text(row["copyright_text"])
    if copyright_text:
        return copyright_text
    return f"{row['source_name']} {row['wallpaper_date']}"


def build_image_url(*, relative_path: str | None) -> str | None:
    if relative_path is None:
        return None
    return f"/images/{relative_path.lstrip('/')}"


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Unsupported integer value type: {type(value)!r}"
    raise TypeError(msg)


def parse_optional_json(value: object) -> dict[str, Any] | None:
    text = optional_text(value)
    if text is None:
        return None
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise TypeError("Audit log state must be a JSON object.")
    return parsed


def parse_content_status(value: object) -> ContentStatus:
    parsed = optional_text(value)
    if parsed not in {"draft", "enabled", "disabled", "deleted"}:
        raise TypeError(f"Unsupported content status: {parsed!r}")
    return cast(ContentStatus, parsed)


def parse_image_status(value: object) -> ImageStatus | None:
    parsed = optional_text(value)
    if parsed is None:
        return None
    if parsed not in {"pending", "ready", "failed"}:
        raise TypeError(f"Unsupported image status: {parsed!r}")
    return cast(ImageStatus, parsed)


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
