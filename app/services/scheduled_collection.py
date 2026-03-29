from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
import json
from sqlite3 import Row

from app.core.config import Settings
from app.domain.collection_sources import COLLECTION_SOURCE_DEFAULT_MARKETS
from app.domain.collection_sources import COLLECTION_SOURCE_TYPES
from app.domain.collection_sources import CollectionSourceType
from app.repositories.admin_collection_repository import AdminCollectionRepository
from app.services.source_collection import utc_now_isoformat

SKIPPED_EXISTING_TASK_STATUSES = frozenset({"queued", "running", "succeeded", "partially_failed"})


@dataclass(frozen=True, slots=True)
class ScheduledCollectionTaskResult:
    source_type: CollectionSourceType
    market_code: str
    date_from: str
    date_to: str
    count: int
    action: str
    task_id: int | None
    reason: str | None


def create_scheduled_collection_tasks(
    *,
    repository: AdminCollectionRepository,
    settings: Settings,
    run_date: date | None = None,
) -> list[ScheduledCollectionTaskResult]:
    scheduled_date = run_date or datetime.now(tz=UTC).date()
    created_at_utc = utc_now_isoformat()
    enabled_sources = [
        source_type
        for source_type in COLLECTION_SOURCE_TYPES
        if is_scheduled_collection_enabled(settings=settings, source_type=source_type)
    ]
    if not enabled_sources:
        raise RuntimeError("No collection sources are enabled by configuration.")

    results: list[ScheduledCollectionTaskResult] = []
    for source_type in enabled_sources:
        source_market_codes = scheduled_market_codes_for_source(
            settings=settings,
            source_type=source_type,
        )
        count = scheduled_task_count_for_source(settings=settings, source_type=source_type)
        recent_rows = repository.list_recent_tasks_for_source(
            source_type=source_type,
            trigger_type="cron",
        )
        backtrack_days = scheduled_backtrack_days_for_source(
            settings=settings,
            source_type=source_type,
        )
        date_from = scheduled_date
        if backtrack_days is not None:
            date_from = scheduled_date - timedelta(days=backtrack_days - 1)

        for market_code in source_market_codes:
            snapshot = build_scheduled_task_snapshot(
                source_type=source_type,
                market_code=market_code,
                date_from=date_from,
                date_to=scheduled_date,
                count=count,
                backtrack_days=backtrack_days,
            )
            if has_existing_scheduled_task(
                rows=recent_rows,
                source_type=source_type,
                market_code=market_code,
                date_from=date_from,
                date_to=scheduled_date,
                backtrack_days=backtrack_days,
            ):
                results.append(
                    ScheduledCollectionTaskResult(
                        source_type=source_type,
                        market_code=market_code,
                        date_from=date_from.isoformat(),
                        date_to=scheduled_date.isoformat(),
                        count=count,
                        action="skipped_existing",
                        task_id=None,
                        reason="same_date_task_already_exists",
                    )
                )
                continue

            task_id = repository.create_queued_task(
                task_type="scheduled_collect",
                source_type=source_type,
                trigger_type="cron",
                triggered_by="cron",
                request_snapshot_json=json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                retry_of_task_id=None,
                created_at_utc=created_at_utc,
            )
            results.append(
                ScheduledCollectionTaskResult(
                    source_type=source_type,
                    market_code=market_code,
                    date_from=date_from.isoformat(),
                    date_to=scheduled_date.isoformat(),
                    count=count,
                    action="created",
                    task_id=task_id,
                    reason=None,
                )
            )
    return results


def build_scheduled_task_snapshot(
    *,
    source_type: CollectionSourceType,
    market_code: str,
    date_from: date,
    date_to: date,
    count: int,
    backtrack_days: int | None,
) -> dict[str, object]:
    return {
        "source_type": source_type,
        "market_code": market_code,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "backtrack_days": backtrack_days,
        "force_refresh": False,
        "count": count,
        "trigger_type": "cron",
    }


def scheduled_task_count_for_source(*, settings: Settings, source_type: CollectionSourceType) -> int:
    if source_type == "bing":
        return settings.collect_bing_scheduled_backtrack_days
    return 1


def scheduled_backtrack_days_for_source(
    *,
    settings: Settings,
    source_type: CollectionSourceType,
) -> int | None:
    if source_type == "bing":
        return settings.collect_bing_scheduled_backtrack_days
    return None


def scheduled_market_codes_for_source(
    *,
    settings: Settings,
    source_type: CollectionSourceType,
) -> tuple[str, ...]:
    if source_type == "bing":
        return settings.collect_bing_markets
    return (COLLECTION_SOURCE_DEFAULT_MARKETS[source_type],)


def has_existing_scheduled_task(
    *,
    rows: list[Row],
    source_type: CollectionSourceType,
    market_code: str,
    date_from: date,
    date_to: date,
    backtrack_days: int | None,
) -> bool:
    date_from_iso = date_from.isoformat()
    date_to_iso = date_to.isoformat()
    for row in rows:
        if str(row["task_status"]) not in SKIPPED_EXISTING_TASK_STATUSES:
            continue
        snapshot = parse_snapshot_json(str(row["request_snapshot_json"] or "{}"))
        if snapshot.get("source_type") != source_type:
            continue
        if snapshot.get("market_code") != market_code:
            continue
        if snapshot.get("date_from") != date_from_iso:
            continue
        if snapshot.get("date_to") != date_to_iso:
            continue
        if snapshot.get("backtrack_days") != backtrack_days:
            continue
        return True
    return False


def parse_snapshot_json(raw_payload: str) -> dict[str, object]:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def is_scheduled_collection_enabled(
    *,
    settings: Settings,
    source_type: CollectionSourceType,
) -> bool:
    if source_type == "bing":
        return settings.collect_bing_enabled
    return settings.collect_nasa_apod_enabled
