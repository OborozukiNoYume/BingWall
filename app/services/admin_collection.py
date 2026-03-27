from __future__ import annotations

from datetime import date
from datetime import datetime
import json
import math
from sqlite3 import Row
from typing import cast

from app.api.errors import ApiError
from app.collectors.bing import BingClient
from app.collectors.nasa_apod import NasaApodClient
from app.collectors.nasa_apod import NasaApodSourceAdapter
from app.core.config import Settings
from app.domain.collection import CollectionRunSummary
from app.domain.collection_sources import COLLECTION_SOURCE_DEFAULT_MARKETS
from app.domain.collection_sources import COLLECTION_SOURCE_TYPES
from app.domain.collection_sources import CollectionSourceType
from app.repositories.admin_collection_repository import AdminCollectionRepository
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.repositories.collection_repository import TaskItemCreateInput
from app.services.bing_collection import BingSourceAdapter
from app.services.source_collection import SourceCollectionService
from app.services.source_collection import utc_now_isoformat
from app.schemas.admin_auth import AdminSessionContext
from app.schemas.admin_collection import AdminCollectionLogListData
from app.schemas.admin_collection import AdminCollectionLogListQuery
from app.schemas.admin_collection import AdminCollectionTaskConsumeData
from app.schemas.admin_collection import AdminCollectionLogSummary
from app.schemas.admin_collection import AdminCollectionTaskCreateData
from app.schemas.admin_collection import AdminCollectionTaskCreateRequest
from app.schemas.admin_collection import AdminCollectionTaskDetailData
from app.schemas.admin_collection import AdminCollectionTaskItemSummary
from app.schemas.admin_collection import AdminCollectionTaskListData
from app.schemas.admin_collection import AdminCollectionTaskListQuery
from app.schemas.admin_collection import AdminCollectionTaskRetryData
from app.schemas.admin_collection import AdminCollectionTaskSnapshot
from app.schemas.admin_collection import AdminCollectionTaskSummary
from app.schemas.admin_collection import CollectionItemResultStatus
from app.schemas.admin_collection import CollectionTaskStatus
from app.schemas.common import Pagination
from app.services.admin_auth import build_request_source


class AdminCollectionService:
    def __init__(
        self,
        repository: AdminCollectionRepository,
        *,
        session_secret: str,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.session_secret = session_secret
        self.settings = settings

    def create_task(
        self,
        *,
        payload: AdminCollectionTaskCreateRequest,
        session: AdminSessionContext,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AdminCollectionTaskCreateData:
        if not is_collection_source_enabled(self.settings, payload.source_type):
            raise ApiError(
                status_code=409,
                error_code="COLLECT_SOURCE_DISABLED",
                message=f"{payload.source_type} 来源当前已关闭，不能创建采集任务",
            )
        created_at_utc = utc_now_isoformat()
        snapshot = payload.model_dump(mode="json")
        task_id = self.repository.create_queued_task(
            task_type="manual_collect",
            source_type=payload.source_type,
            trigger_type="admin",
            triggered_by=session.username,
            request_snapshot_json=json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            retry_of_task_id=None,
            created_at_utc=created_at_utc,
        )
        self.repository.insert_audit_log(
            admin_user_id=session.admin_user_id,
            action_type="collection_task_created",
            target_type="collection_task",
            target_id=str(task_id),
            before_state_json=None,
            after_state_json=json.dumps(
                {
                    "task_status": "queued",
                    "request_snapshot": snapshot,
                },
                ensure_ascii=False,
            ),
            request_source=build_request_source(
                client_ip=client_ip,
                user_agent=user_agent,
                secret=self.session_secret,
            ),
            trace_id=trace_id,
            created_at_utc=created_at_utc,
        )
        return AdminCollectionTaskCreateData(task_id=task_id, task_status="queued")

    def list_tasks(
        self, *, query: AdminCollectionTaskListQuery
    ) -> tuple[AdminCollectionTaskListData, Pagination]:
        rows, total = self.repository.list_tasks(query=query)
        items = [self._build_task_summary(row) for row in rows]
        total_pages = math.ceil(total / query.page_size) if total else 0
        pagination = Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
        )
        return AdminCollectionTaskListData(items=items), pagination

    def get_task_detail(self, *, task_id: int) -> AdminCollectionTaskDetailData:
        row = self.repository.get_task(task_id=task_id)
        if row is None:
            raise ApiError(
                status_code=404,
                error_code="COLLECT_TASK_NOT_FOUND",
                message="采集任务不存在",
            )
        snapshot = parse_task_snapshot(row)
        items = [
            AdminCollectionTaskItemSummary(
                id=int(item_row["id"]),
                source_item_key=optional_text(item_row["source_item_key"]),
                action_name=str(item_row["action_name"]),
                result_status=parse_collection_item_result_status(item_row["result_status"]),
                dedupe_hit_type=optional_text(item_row["dedupe_hit_type"]),
                db_write_result=optional_text(item_row["db_write_result"]),
                file_write_result=optional_text(item_row["file_write_result"]),
                failure_reason=optional_text(item_row["failure_reason"]),
                occurred_at_utc=str(item_row["occurred_at_utc"]),
            )
            for item_row in self.repository.list_task_items(task_id=task_id)
        ]
        summary = self._build_task_summary(row)
        return AdminCollectionTaskDetailData(
            **summary.model_dump(),
            request_snapshot=snapshot,
            items=items,
        )

    def retry_task(
        self,
        *,
        task_id: int,
        session: AdminSessionContext,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AdminCollectionTaskRetryData:
        row = self.repository.get_task(task_id=task_id)
        if row is None:
            raise ApiError(
                status_code=404,
                error_code="COLLECT_TASK_NOT_FOUND",
                message="采集任务不存在",
            )

        current_status = str(row["task_status"])
        if current_status not in {"failed", "partially_failed"}:
            raise ApiError(
                status_code=409,
                error_code="COLLECT_TASK_RETRY_NOT_ALLOWED",
                message="只有失败或部分失败的任务允许重试",
            )

        source_type = cast(CollectionSourceType, str(row["source_type"]))
        if not is_collection_source_enabled(self.settings, source_type):
            raise ApiError(
                status_code=409,
                error_code="COLLECT_SOURCE_DISABLED",
                message=f"{source_type} 来源当前已关闭，不能创建重试任务",
            )

        created_at_utc = utc_now_isoformat()
        new_task_id = self.repository.create_queued_task(
            task_type=str(row["task_type"]),
            source_type=source_type,
            trigger_type="admin",
            triggered_by=session.username,
            request_snapshot_json=str(row["request_snapshot_json"] or "{}"),
            retry_of_task_id=task_id,
            created_at_utc=created_at_utc,
        )
        self.repository.insert_audit_log(
            admin_user_id=session.admin_user_id,
            action_type="collection_task_retried",
            target_type="collection_task",
            target_id=str(new_task_id),
            before_state_json=json.dumps(
                {
                    "retry_of_task_id": task_id,
                    "original_task_status": current_status,
                },
                ensure_ascii=False,
            ),
            after_state_json=json.dumps(
                {
                    "task_status": "queued",
                    "retry_of_task_id": task_id,
                },
                ensure_ascii=False,
            ),
            request_source=build_request_source(
                client_ip=client_ip,
                user_agent=user_agent,
                secret=self.session_secret,
            ),
            trace_id=trace_id,
            created_at_utc=created_at_utc,
        )
        return AdminCollectionTaskRetryData(
            task_id=new_task_id,
            task_status="queued",
            retry_of_task_id=task_id,
        )

    def list_logs(
        self, *, query: AdminCollectionLogListQuery
    ) -> tuple[AdminCollectionLogListData, Pagination]:
        rows, total = self.repository.list_logs(query=query)
        items = [
            AdminCollectionLogSummary(
                id=int(row["id"]),
                task_id=int(row["task_id"]),
                task_status=str(row["task_status"]),
                source_type=str(row["source_type"]),
                trigger_type=str(row["trigger_type"]),
                source_item_key=optional_text(row["source_item_key"]),
                action_name=str(row["action_name"]),
                result_status=parse_collection_item_result_status(row["result_status"]),
                dedupe_hit_type=optional_text(row["dedupe_hit_type"]),
                db_write_result=optional_text(row["db_write_result"]),
                file_write_result=optional_text(row["file_write_result"]),
                failure_reason=optional_text(row["failure_reason"]),
                occurred_at_utc=str(row["occurred_at_utc"]),
            )
            for row in rows
        ]
        total_pages = math.ceil(total / query.page_size) if total else 0
        pagination = Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
        )
        return AdminCollectionLogListData(items=items), pagination

    def _build_task_summary(self, row: Row) -> AdminCollectionTaskSummary:
        snapshot = parse_task_snapshot(row)
        return AdminCollectionTaskSummary(
            id=int(row["id"]),
            task_type=str(row["task_type"]),
            source_type=str(row["source_type"]),
            trigger_type=str(row["trigger_type"]),
            triggered_by=optional_text(row["triggered_by"]),
            task_status=parse_collection_task_status(row["task_status"]),
            market_code=snapshot.market_code if snapshot.market_code else None,
            date_from=snapshot.date_from,
            date_to=snapshot.date_to,
            force_refresh=snapshot.force_refresh,
            started_at_utc=optional_text(row["started_at_utc"]),
            finished_at_utc=optional_text(row["finished_at_utc"]),
            success_count=int(row["success_count"]),
            duplicate_count=int(row["duplicate_count"]),
            failure_count=int(row["failure_count"]),
            error_summary=optional_text(row["error_summary"]),
            retry_of_task_id=optional_int(row["retry_of_task_id"]),
            created_at_utc=str(row["created_at_utc"]),
            updated_at_utc=str(row["updated_at_utc"]),
        )


class ManualCollectionTaskConsumer:
    def __init__(
        self,
        *,
        repository: CollectionRepository,
        services: dict[str, SourceCollectionService],
        supported_source_types: tuple[str, ...] = COLLECTION_SOURCE_TYPES,
    ) -> None:
        self.repository = repository
        self.services = services
        self.supported_source_types = supported_source_types

    def consume_next_queued_task(self) -> CollectionRunSummary | None:
        task_row = self.repository.claim_next_queued_task_for_sources(
            source_types=self.supported_source_types,
            claimed_at_utc=utc_now_isoformat(),
        )
        if task_row is None:
            return None
        return self.consume_task(task_id=int(task_row["id"]))

    def consume_task(self, *, task_id: int) -> CollectionRunSummary:
        task_row = self.repository.get_collection_task(task_id=task_id)
        if task_row is None:
            raise RuntimeError(f"Collection task {task_id} does not exist.")

        source_type = str(task_row["source_type"])
        service = self.services.get(source_type)
        if service is None:
            return self._mark_task_failed(
                task_id=task_id,
                failure_reason=f"Collection source is disabled or unsupported: {source_type}",
            )

        try:
            snapshot = parse_task_snapshot(task_row)
            date_from = parse_iso_date(snapshot.date_from)
            date_to = parse_iso_date(snapshot.date_to)
            count = snapshot.count
            if count is None:
                if date_from is not None and date_to is not None:
                    count = (date_to - date_from).days + 1
                else:
                    count = 1
            market_code = snapshot.market_code or COLLECTION_SOURCE_DEFAULT_MARKETS.get(
                cast(CollectionSourceType, source_type),
                "",
            )
            if not market_code:
                raise RuntimeError(f"Queued {source_type} collection task is missing market_code.")
        except Exception as exc:
            return self._mark_task_failed(task_id=task_id, failure_reason=str(exc))

        return service.collect_existing_task(
            task_id=task_id,
            market_code=market_code,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )

    def _mark_task_failed(self, *, task_id: int, failure_reason: str) -> CollectionRunSummary:
        failed_at_utc = utc_now_isoformat()
        self.repository.create_task_item(
            TaskItemCreateInput(
                task_id=task_id,
                source_item_key=None,
                action_name="consume_task",
                result_status="failed",
                dedupe_hit_type=None,
                db_write_result=None,
                file_write_result=None,
                failure_reason=failure_reason,
                occurred_at_utc=failed_at_utc,
            )
        )
        self.repository.finish_collection_task(
            task_id=task_id,
            task_status="failed",
            success_count=0,
            duplicate_count=0,
            failure_count=1,
            error_summary=failure_reason,
            finished_at_utc=failed_at_utc,
        )
        return CollectionRunSummary(
            task_id=task_id,
            task_status="failed",
            success_count=0,
            duplicate_count=0,
            failure_count=1,
            error_summary=failure_reason,
        )


class AdminCollectionExecutionService:
    def __init__(
        self,
        *,
        repository: CollectionRepository,
        audit_repository: AdminCollectionRepository,
        consumer: ManualCollectionTaskConsumer,
        session_secret: str,
    ) -> None:
        self.repository = repository
        self.audit_repository = audit_repository
        self.consumer = consumer
        self.session_secret = session_secret

    def consume_task(
        self,
        *,
        task_id: int,
        session: AdminSessionContext,
        trace_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AdminCollectionTaskConsumeData:
        task_row = self.repository.get_collection_task(task_id=task_id)
        if task_row is None:
            raise ApiError(
                status_code=404,
                error_code="COLLECT_TASK_NOT_FOUND",
                message="采集任务不存在",
            )

        if str(task_row["task_status"]) != "queued":
            raise ApiError(
                status_code=409,
                error_code="COLLECT_TASK_CONSUME_NOT_ALLOWED",
                message="只有 queued 状态的任务允许手动触发执行",
            )

        claimed_row = self.repository.claim_task_by_id(
            task_id=task_id,
            claimed_at_utc=utc_now_isoformat(),
        )
        if claimed_row is None:
            latest_row = self.repository.get_collection_task(task_id=task_id)
            if latest_row is None:
                raise ApiError(
                    status_code=404,
                    error_code="COLLECT_TASK_NOT_FOUND",
                    message="采集任务不存在",
                )
            if str(latest_row["task_status"]) != "queued":
                raise ApiError(
                    status_code=409,
                    error_code="COLLECT_TASK_CONSUME_NOT_ALLOWED",
                    message="任务状态已变化，不能重复手动触发",
                )
            raise ApiError(
                status_code=409,
                error_code="COLLECT_TASK_SOURCE_BUSY",
                message="同来源已有运行中的任务，请稍后再试",
            )

        summary = self.consumer.consume_task(task_id=task_id)
        consumed_at_utc = utc_now_isoformat()
        self.audit_repository.insert_audit_log(
            admin_user_id=session.admin_user_id,
            action_type="collection_task_consumed",
            target_type="collection_task",
            target_id=str(task_id),
            before_state_json=json.dumps(
                {
                    "task_status": "queued",
                },
                ensure_ascii=False,
            ),
            after_state_json=json.dumps(
                {
                    "task_status": summary.task_status,
                    "success_count": summary.success_count,
                    "duplicate_count": summary.duplicate_count,
                    "failure_count": summary.failure_count,
                    "error_summary": summary.error_summary,
                },
                ensure_ascii=False,
            ),
            request_source=build_request_source(
                client_ip=client_ip,
                user_agent=user_agent,
                secret=self.session_secret,
            ),
            trace_id=trace_id,
            created_at_utc=consumed_at_utc,
        )
        return AdminCollectionTaskConsumeData(
            task_id=summary.task_id,
            task_status=parse_collection_task_status(summary.task_status),
            success_count=summary.success_count,
            duplicate_count=summary.duplicate_count,
            failure_count=summary.failure_count,
            error_summary=summary.error_summary,
        )


def build_collection_source_services(
    *,
    settings: Settings,
    repository: CollectionRepository,
    storage: FileStorage,
) -> dict[str, SourceCollectionService]:
    services: dict[str, SourceCollectionService] = {}
    if settings.collect_bing_enabled:
        services["bing"] = SourceCollectionService(
            repository=repository,
            storage=storage,
            adapter=BingSourceAdapter(
                client=BingClient(timeout_seconds=settings.collect_bing_timeout_seconds)
            ),
            max_download_retries=settings.collect_bing_max_download_retries,
            auto_publish_enabled=settings.collect_auto_publish_enabled,
        )
    if settings.collect_nasa_apod_enabled:
        services["nasa_apod"] = SourceCollectionService(
            repository=repository,
            storage=storage,
            adapter=NasaApodSourceAdapter(
                client=NasaApodClient(
                    api_key=settings.collect_nasa_apod_api_key.get_secret_value(),
                    timeout_seconds=settings.collect_nasa_apod_timeout_seconds,
                )
            ),
            max_download_retries=settings.collect_nasa_apod_max_download_retries,
            auto_publish_enabled=settings.collect_auto_publish_enabled,
        )
    return services


def is_collection_source_enabled(settings: Settings, source_type: CollectionSourceType) -> bool:
    if source_type == "bing":
        return settings.collect_bing_enabled
    return settings.collect_nasa_apod_enabled


def parse_task_snapshot(row: Row) -> AdminCollectionTaskSnapshot:
    source_type = cast(CollectionSourceType, str(row["source_type"]))
    raw_payload = row["request_snapshot_json"]
    snapshot_data = {
        "source_type": source_type,
        "market_code": COLLECTION_SOURCE_DEFAULT_MARKETS[source_type],
    }
    if raw_payload:
        try:
            parsed = json.loads(str(raw_payload))
            if isinstance(parsed, dict):
                snapshot_data.update(parsed)
        except json.JSONDecodeError:
            pass
    return AdminCollectionTaskSnapshot.model_validate(snapshot_data)


def parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def parse_collection_item_result_status(value: object) -> CollectionItemResultStatus:
    normalized = str(value)
    if normalized not in {"succeeded", "duplicated", "failed"}:
        raise TypeError(f"Unsupported collection item result status: {normalized}")
    return cast(CollectionItemResultStatus, normalized)


def parse_collection_task_status(value: object) -> CollectionTaskStatus:
    normalized = str(value)
    if normalized not in {"queued", "running", "succeeded", "partially_failed", "failed"}:
        raise TypeError(f"Unsupported collection task status: {normalized}")
    return cast(CollectionTaskStatus, normalized)
