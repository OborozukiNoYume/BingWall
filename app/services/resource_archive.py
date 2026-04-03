from __future__ import annotations

from datetime import UTC
from datetime import datetime
import hashlib
import logging
from pathlib import Path
import shutil
from typing import cast
from typing import TypedDict

from app.repositories.health_repository import HealthRepository
from app.services.image_variants import load_image_bytes
from app.services.resource_paths import build_resource_relative_path
from app.services.resource_paths import resolve_resource_path_key
from app.domain.resource_variants import ResourceType

logger = logging.getLogger(__name__)


class ArchiveCleanupSummary(TypedDict):
    scanned_at_utc: str
    archived_resource_count: int
    damaged_resource_count: int
    tmp_deleted_count: int
    empty_deleted_count: int
    duplicate_deleted_count: int
    orphan_quarantined_count: int
    skipped_conflict_count: int


class ResourceArchiveService:
    def __init__(
        self,
        repository: HealthRepository,
        *,
        tmp_dir: Path,
        public_dir: Path,
        failed_dir: Path,
    ) -> None:
        self.repository = repository
        self.tmp_dir = tmp_dir
        self.public_dir = public_dir
        self.failed_dir = failed_dir

    def archive_and_cleanup(self) -> ArchiveCleanupSummary:
        scanned_at_utc = datetime.now(UTC).replace(microsecond=0)
        processed_at_utc = scanned_at_utc.isoformat().replace("+00:00", "Z")

        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

        archived_resource_count = 0
        damaged_resource_count = 0
        tmp_deleted_count = 0
        empty_deleted_count = 0
        duplicate_deleted_count = 0
        orphan_quarantined_count = 0
        skipped_conflict_count = 0

        protected_digests = self._build_protected_digest_index()
        referenced_paths: set[str] = set()

        for row in self.repository.list_local_resources_for_archive():
            relative_path = str(row["relative_path"])
            referenced_paths.add(relative_path)

            if str(row["image_status"]) != "ready":
                continue

            expected_relative_path = build_resource_relative_path(
                source_type=str(row["source_type"]),
                wallpaper_date=datetime.strptime(str(row["wallpaper_date"]), "%Y-%m-%d").date(),
                market_code=str(row["market_code"]),
                path_key=resolve_resource_path_key(
                    source_type=str(row["source_type"]),
                    market_code=str(row["market_code"]),
                    source_key=str(row["source_key"]),
                    canonical_key=str(row["canonical_key"]) if row["canonical_key"] else None,
                ),
                resource_type=cast(ResourceType, str(row["resource_type"])),
                file_ext=str(row["file_ext"]),
                width=_optional_int(row["width"]),
                height=_optional_int(row["height"]),
                variant_key=str(row["variant_key"] or ""),
            )
            current_path = self.public_dir / relative_path
            target_path = self.public_dir / expected_relative_path
            resource_id = int(row["resource_id"])
            wallpaper_id = int(row["wallpaper_id"])

            if relative_path != expected_relative_path and current_path.is_file():
                move_result = self._move_ready_resource_to_expected_path(
                    current_path=current_path,
                    target_path=target_path,
                    relative_path=relative_path,
                    expected_relative_path=expected_relative_path,
                    protected_digests=protected_digests,
                    processed_at_utc=processed_at_utc,
                    resource_id=resource_id,
                )
                if move_result == "archived":
                    archived_resource_count += 1
                    referenced_paths.remove(relative_path)
                    referenced_paths.add(expected_relative_path)
                    relative_path = expected_relative_path
                    current_path = target_path
                elif move_result == "skipped_conflict":
                    skipped_conflict_count += 1

            if current_path.is_file():
                validation_failure = self._validate_ready_resource_file(
                    path=current_path,
                    expected_size_bytes=_optional_int(row["file_size_bytes"]),
                )
                if validation_failure is not None:
                    damaged_resource_count += 1
                    quarantine_relative_path = self._build_quarantine_relative_path(
                        category="invalid",
                        relative_path=relative_path,
                    )
                    self._move_file(
                        source=current_path,
                        destination=self.failed_dir / quarantine_relative_path,
                    )
                    self.repository.mark_resource_failed_and_sync(
                        resource_id=resource_id,
                        wallpaper_id=wallpaper_id,
                        failure_reason=validation_failure,
                        processed_at_utc=processed_at_utc,
                    )
                    protected_digests.pop(relative_path, None)
                    referenced_paths.discard(relative_path)
            else:
                self.repository.mark_resource_failed_and_sync(
                    resource_id=resource_id,
                    wallpaper_id=wallpaper_id,
                    failure_reason=f"resource archive missing file: {relative_path}",
                    processed_at_utc=processed_at_utc,
                )
                damaged_resource_count += 1
                protected_digests.pop(relative_path, None)
                referenced_paths.discard(relative_path)

        for file_path in self._iter_files(self.tmp_dir):
            file_path.unlink()
            tmp_deleted_count += 1
        self._prune_empty_directories(self.tmp_dir)

        orphan_digests = set(protected_digests.values())
        for file_path in self._iter_files(self.failed_dir):
            file_size = file_path.stat().st_size
            if file_size <= 0:
                file_path.unlink()
                empty_deleted_count += 1
                continue
            file_hash = self._hash_file(file_path)
            if file_hash in orphan_digests:
                file_path.unlink()
                duplicate_deleted_count += 1
                continue
            orphan_digests.add(file_hash)
        self._prune_empty_directories(self.failed_dir)

        for file_path in self._iter_files(self.public_dir):
            relative_path = str(file_path.relative_to(self.public_dir))
            if relative_path in referenced_paths:
                continue
            cleanup_result = self._cleanup_unreferenced_file(
                file_path=file_path,
                relative_path=relative_path,
                orphan_digests=orphan_digests,
            )
            if cleanup_result == "empty_deleted":
                empty_deleted_count += 1
            elif cleanup_result == "duplicate_deleted":
                duplicate_deleted_count += 1
            elif cleanup_result == "orphan_quarantined":
                orphan_quarantined_count += 1
        self._prune_empty_directories(self.public_dir)
        self._prune_empty_directories(self.failed_dir)

        return {
            "scanned_at_utc": scanned_at_utc.isoformat().replace("+00:00", "Z"),
            "archived_resource_count": archived_resource_count,
            "damaged_resource_count": damaged_resource_count,
            "tmp_deleted_count": tmp_deleted_count,
            "empty_deleted_count": empty_deleted_count,
            "duplicate_deleted_count": duplicate_deleted_count,
            "orphan_quarantined_count": orphan_quarantined_count,
            "skipped_conflict_count": skipped_conflict_count,
        }

    def _build_protected_digest_index(self) -> dict[str, str]:
        protected: dict[str, str] = {}
        for row in self.repository.list_ready_local_resources_with_hashes():
            relative_path = str(row["relative_path"])
            content_hash = str(row["content_hash"] or "").strip()
            if content_hash:
                protected[relative_path] = content_hash
                continue
            file_path = self.public_dir / relative_path
            if not file_path.is_file():
                continue
            protected[relative_path] = self._hash_file(file_path)
        return protected

    def _move_ready_resource_to_expected_path(
        self,
        *,
        current_path: Path,
        target_path: Path,
        relative_path: str,
        expected_relative_path: str,
        protected_digests: dict[str, str],
        processed_at_utc: str,
        resource_id: int,
    ) -> str:
        source_hash = self._hash_file(current_path)
        if target_path.is_file():
            target_hash = self._hash_file(target_path)
            if source_hash != target_hash:
                logger.warning(
                    "Skip archive move because target already exists with different content: %s -> %s",
                    relative_path,
                    expected_relative_path,
                )
                return "skipped_conflict"
            current_path.unlink()
        else:
            self._move_file(source=current_path, destination=target_path)

        self.repository.update_image_resource_relative_path(
            resource_id=resource_id,
            relative_path=expected_relative_path,
            filename=target_path.name,
            file_ext=target_path.suffix.lstrip(".").lower() or "jpg",
            updated_at_utc=processed_at_utc,
        )
        protected_digests.pop(relative_path, None)
        protected_digests[expected_relative_path] = source_hash
        return "archived"

    def _validate_ready_resource_file(
        self,
        *,
        path: Path,
        expected_size_bytes: int | None,
    ) -> str | None:
        file_size = path.stat().st_size
        if file_size <= 0:
            return f"resource archive detected empty file: {path.name}"
        if expected_size_bytes is not None and file_size != expected_size_bytes:
            return f"resource archive detected size mismatch: {path.name}"
        try:
            load_image_bytes(path.read_bytes(), fallback_mime_type=None)
        except Exception as exc:
            return f"resource archive detected corrupted image: {path.name}: {exc}"
        return None

    def _cleanup_unreferenced_file(
        self,
        *,
        file_path: Path,
        relative_path: str,
        orphan_digests: set[str],
    ) -> str:
        file_size = file_path.stat().st_size
        if file_size <= 0:
            file_path.unlink()
            return "empty_deleted"

        file_hash = self._hash_file(file_path)
        if file_hash in orphan_digests:
            file_path.unlink()
            return "duplicate_deleted"

        orphan_digests.add(file_hash)
        quarantine_relative_path = self._build_quarantine_relative_path(
            category="orphaned",
            relative_path=relative_path,
        )
        self._move_file(
            source=file_path,
            destination=self.failed_dir / quarantine_relative_path,
        )
        return "orphan_quarantined"

    def _build_quarantine_relative_path(self, *, category: str, relative_path: str) -> str:
        original_path = Path(relative_path)
        target = Path(category) / original_path
        if not (self.failed_dir / target).exists():
            return str(target)
        stem = original_path.stem
        suffix = original_path.suffix
        index = 1
        while True:
            candidate = Path(category) / original_path.parent / f"{stem}__{index}{suffix}"
            if not (self.failed_dir / candidate).exists():
                return str(candidate)
            index += 1

    def _move_file(self, *, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    def _hash_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _iter_files(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        return sorted(path for path in root.rglob("*") if path.is_file())

    def _prune_empty_directories(self, root: Path) -> None:
        if not root.exists():
            return
        for directory in sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            if any(directory.iterdir()):
                continue
            directory.rmdir()


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Unsupported integer value: {value!r}"
    raise TypeError(msg)
