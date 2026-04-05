from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
import argparse
import math
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

from app.repositories.admin_content_repository import AdminContentRepository
from app.repositories.migrations.runner import migrate_database
from app.repositories.public_repository import PublicRepository
from app.schemas.admin_content import AdminWallpaperListQuery
from app.schemas.public import PublicWallpaperListQuery
from app.services.admin_content import AdminContentService
from app.services.public_catalog import PublicCatalogService
from app.services.resource_locator import ResourceLocator

DEFAULT_WALLPAPER_COUNT = 12_000
DEFAULT_ITERATIONS = 30
DEFAULT_WARMUP = 5
DEFAULT_PAGE_SIZE = 20
DEFAULT_MARKET_CODE = "en-US"
DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
DEFAULT_SESSION_SECRET = "benchmark-session-secret"

MARKETS = (
    "zh-CN",
    "en-US",
    "ja-JP",
    "en-GB",
    "de-DE",
    "fr-FR",
    "en-CA",
    "en-AU",
)

THEMES = (
    ("aurora", "Aurora"),
    ("coast", "Coast"),
    ("forest", "Forest"),
    ("desert", "Desert"),
    ("city", "City"),
    ("galaxy", "Galaxy"),
)

SEASONS = (
    ("season-spring", "Spring"),
    ("season-summer", "Summer"),
    ("season-autumn", "Autumn"),
    ("season-winter", "Winter"),
)

CURATION_TAGS = (
    ("collection-editorial", "Editorial"),
    ("collection-spotlight", "Spotlight"),
)

RESOLUTION_CYCLE = (
    (3840, 2160),
    (2560, 1440),
    (1920, 1080),
    (1366, 768),
)


@dataclass(frozen=True)
class DatasetSummary:
    database_path: Path
    wallpaper_count: int
    visible_wallpaper_count: int
    localization_count: int
    image_resource_count: int
    wallpaper_tag_count: int
    tag_count: int
    date_from: date
    date_to: date


@dataclass(frozen=True)
class ScenarioThreshold:
    p95_ms: float
    p99_ms: float


@dataclass(frozen=True)
class PublicScenario:
    name: str
    description: str
    threshold: ScenarioThreshold
    queries: tuple[PublicWallpaperListQuery, ...]
    keyword_sensitive: bool = False


@dataclass(frozen=True)
class AdminScenario:
    name: str
    description: str
    threshold: ScenarioThreshold
    queries: tuple[AdminWallpaperListQuery, ...]
    keyword_sensitive: bool = False


@dataclass(frozen=True)
class BenchmarkResult:
    category: str
    name: str
    description: str
    runs: int
    total_hits_preview: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    threshold: ScenarioThreshold
    evaluation: str
    keyword_sensitive: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a representative SQLite dataset for BingWall and benchmark "
            "public/admin list queries."
        )
    )
    parser.add_argument(
        "--wallpapers",
        type=int,
        default=DEFAULT_WALLPAPER_COUNT,
        help=f"Number of wallpapers to seed. Default: {DEFAULT_WALLPAPER_COUNT}.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Measured iterations per scenario. Default: {DEFAULT_ITERATIONS}.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP,
        help=f"Warmup iterations per scenario. Default: {DEFAULT_WARMUP}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_args(args)

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="bingwall-benchmark-") as temp_dir:
        summary = build_dataset(
            root=Path(temp_dir),
            wallpaper_count=args.wallpapers,
        )
        public_repository = PublicRepository(summary.database_path)
        admin_repository = AdminContentRepository(summary.database_path)
        public_service = PublicCatalogService(
            public_repository,
            resource_locator=ResourceLocator(),
        )
        admin_service = AdminContentService(
            admin_repository,
            session_secret=DEFAULT_SESSION_SECRET,
            resource_locator=ResourceLocator(),
        )
        try:
            results = run_benchmarks(
                summary=summary,
                public_service=public_service,
                admin_service=admin_service,
                warmup=args.warmup,
                iterations=args.iterations,
            )
        finally:
            public_repository.close()
            admin_repository.close()

        total_elapsed_ms = (time.perf_counter() - started) * 1000
        print_report(summary=summary, results=results, total_elapsed_ms=total_elapsed_ms)

    return 0


def validate_args(args: argparse.Namespace) -> None:
    if args.wallpapers < 800:
        raise SystemExit("--wallpapers must be at least 800 to keep the sample representative.")
    if args.iterations < 5:
        raise SystemExit("--iterations must be at least 5.")
    if args.warmup < 0:
        raise SystemExit("--warmup must be zero or greater.")


def build_dataset(*, root: Path, wallpaper_count: int) -> DatasetSummary:
    database_path = root / "data" / "bingwall.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    migrate_database(database_path)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA journal_mode = WAL;")
        connection.execute("PRAGMA synchronous = NORMAL;")
        connection.execute("PRAGMA temp_store = MEMORY;")

        summary = seed_benchmark_dataset(
            connection=connection,
            wallpaper_count=wallpaper_count,
        )
        connection.commit()
        return summary
    finally:
        connection.close()


def seed_benchmark_dataset(
    *,
    connection: sqlite3.Connection,
    wallpaper_count: int,
) -> DatasetSummary:
    tags = [*THEMES, *SEASONS, *CURATION_TAGS]
    tag_rows = []
    tag_id_by_key: dict[str, int] = {}
    current_time = utc_now()
    now_utc = isoformat_utc(current_time)
    for index, (tag_key, tag_name) in enumerate(tags, start=1):
        tag_rows.append((
            index,
            tag_key,
            tag_name,
            "benchmark",
            "enabled",
            index,
            now_utc,
            now_utc,
        ))
        tag_id_by_key[tag_key] = index

    connection.executemany(
        """
        INSERT INTO tags (
            id,
            tag_key,
            tag_name,
            tag_category,
            status,
            sort_weight,
            created_at_utc,
            updated_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        tag_rows,
    )

    day_span = math.ceil(wallpaper_count / len(MARKETS))
    end_date = current_time.date()
    start_date = end_date - timedelta(days=day_span - 1)

    wallpaper_rows: list[tuple[object, ...]] = []
    localization_rows: list[tuple[object, ...]] = []
    resource_rows: list[tuple[object, ...]] = []
    wallpaper_tag_rows: list[tuple[object, ...]] = []
    visible_count = 0
    resource_id = 1

    for index in range(wallpaper_count):
        wallpaper_id = index + 1
        market_code = MARKETS[index % len(MARKETS)]
        day_offset = index // len(MARKETS)
        wallpaper_date = start_date + timedelta(days=day_offset)
        theme_key, theme_label = THEMES[(day_offset + index) % len(THEMES)]
        season_key, season_label = SEASONS[(day_offset // 45 + index) % len(SEASONS)]
        collection_key, collection_label = CURATION_TAGS[(day_offset + index) % len(CURATION_TAGS)]
        width, height = RESOLUTION_CYCLE[index % len(RESOLUTION_CYCLE)]

        status_bucket = index % 10
        if status_bucket <= 5:
            content_status = "enabled"
            is_public = 1
            visible_count += 1
        elif status_bucket <= 7:
            content_status = "enabled"
            is_public = 0
        elif status_bucket == 8:
            content_status = "disabled"
            is_public = 0
        else:
            content_status = "draft"
            is_public = 0

        published_at = datetime.combine(
            wallpaper_date,
            datetime.min.time(),
            tzinfo=UTC,
        ) + timedelta(hours=index % 24)
        published_at_utc = isoformat_utc(published_at)
        title = f"{theme_label} Benchmark {day_offset:04d} {market_code}"
        subtitle = f"{season_label} showcase {day_offset:04d}"
        descriptor = "Editorial" if index % 2 == 0 else "Spotlight"
        description = (
            f"{descriptor} {theme_label} wallpaper sample for {market_code} "
            f"captured during {season_label.lower()}."
        )
        canonical_key = f"benchmark:{wallpaper_date.isoformat()}:{market_code}:{wallpaper_id}"
        source_key = f"bing:{market_code}:{wallpaper_date.isoformat()}:{wallpaper_id}"
        slug = slugify(title)
        original_resource_id = resource_id
        thumbnail_resource_id = resource_id + 1
        resource_id += 2

        wallpaper_rows.append((
            wallpaper_id,
            "bing",
            source_key,
            canonical_key,
            market_code,
            wallpaper_date.isoformat(),
            title,
            subtitle,
            description,
            f"{title} copyright",
            "Bing",
            content_status,
            is_public,
            1,
            published_at_utc,
            "2100-01-01T00:00:00Z",
            original_resource_id,
            "https://www.bing.com/example",
            f"https://www.bing.com/{slug}.jpg",
            width,
            height,
            "ready",
            published_at_utc,
            published_at_utc,
        ))

        localization_rows.append((
            wallpaper_id,
            market_code,
            source_key,
            title,
            subtitle,
            description,
            f"{title} copyright",
            published_at_utc,
            f"{theme_label} location {market_code}",
            "https://www.bing.com/example",
            f"https://www.bing.com/{slug}-portrait.jpg",
            "{}",
            published_at_utc,
            published_at_utc,
        ))
        fallback_market = DEFAULT_MARKET_CODE if market_code != DEFAULT_MARKET_CODE else "zh-CN"
        localization_rows.append((
            wallpaper_id,
            fallback_market,
            f"bing:{fallback_market}:{wallpaper_date.isoformat()}:{wallpaper_id}",
            f"{theme_label} Localized {day_offset:04d}",
            f"{season_label} localized view",
            (
                f"{descriptor} localized {theme_label.lower()} wallpaper sample "
                f"for {fallback_market}."
            ),
            f"{theme_label} localized copyright",
            published_at_utc,
            f"{theme_label} location {fallback_market}",
            "https://www.bing.com/example",
            f"https://www.bing.com/{slug}-localized-portrait.jpg",
            "{}",
            published_at_utc,
            published_at_utc,
        ))

        original_relative_path = (
            f"bing/{wallpaper_date.year:04d}/{wallpaper_date.month:02d}/{market_code}/{slug}.jpg"
        )
        thumbnail_relative_path = (
            f"bing/{wallpaper_date.year:04d}/{wallpaper_date.month:02d}/"
            f"{market_code}/{slug}--thumbnail.jpg"
        )
        resource_rows.append((
            original_resource_id,
            wallpaper_id,
            "original",
            "",
            "local",
            original_relative_path,
            Path(original_relative_path).name,
            "jpg",
            "image/jpeg",
            1_024,
            width,
            height,
            f"https://www.bing.com/{slug}.jpg",
            f"source-{wallpaper_id}-original",
            f"content-{wallpaper_id}-original",
            published_at_utc,
            "passed",
            "ready",
            None,
            published_at_utc,
            published_at_utc,
            published_at_utc,
        ))
        resource_rows.append((
            thumbnail_resource_id,
            wallpaper_id,
            "thumbnail",
            "",
            "local",
            thumbnail_relative_path,
            Path(thumbnail_relative_path).name,
            "jpg",
            "image/jpeg",
            256,
            480,
            270,
            None,
            None,
            f"content-{wallpaper_id}-thumbnail",
            published_at_utc,
            "passed",
            "ready",
            None,
            published_at_utc,
            published_at_utc,
            published_at_utc,
        ))

        wallpaper_tag_rows.extend([
            (wallpaper_id, tag_id_by_key[theme_key], published_at_utc, "benchmark"),
            (wallpaper_id, tag_id_by_key[season_key], published_at_utc, "benchmark"),
            (wallpaper_id, tag_id_by_key[collection_key], published_at_utc, "benchmark"),
        ])

    connection.executemany(
        """
        INSERT INTO wallpapers (
            id,
            source_type,
            source_key,
            canonical_key,
            market_code,
            wallpaper_date,
            title,
            subtitle,
            description,
            copyright_text,
            source_name,
            content_status,
            is_public,
            is_downloadable,
            publish_start_at_utc,
            publish_end_at_utc,
            default_resource_id,
            origin_page_url,
            origin_image_url,
            origin_width,
            origin_height,
            resource_status,
            created_at_utc,
            updated_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        wallpaper_rows,
    )
    connection.executemany(
        """
        INSERT INTO wallpaper_localizations (
            wallpaper_id,
            market_code,
            source_key,
            title,
            subtitle,
            description,
            copyright_text,
            published_at_utc,
            location_text,
            origin_page_url,
            portrait_image_url,
            raw_extra_json,
            created_at_utc,
            updated_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        localization_rows,
    )
    connection.executemany(
        """
        INSERT INTO image_resources (
            id,
            wallpaper_id,
            resource_type,
            variant_key,
            storage_backend,
            relative_path,
            filename,
            file_ext,
            mime_type,
            file_size_bytes,
            width,
            height,
            source_url,
            source_url_hash,
            content_hash,
            downloaded_at_utc,
            integrity_check_result,
            image_status,
            failure_reason,
            last_processed_at_utc,
            created_at_utc,
            updated_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        resource_rows,
    )
    connection.executemany(
        """
        INSERT INTO wallpaper_tags (
            wallpaper_id,
            tag_id,
            created_at_utc,
            created_by
        )
        VALUES (?, ?, ?, ?);
        """,
        wallpaper_tag_rows,
    )

    database_filename = str(connection.execute("PRAGMA database_list;").fetchone()[2])
    return DatasetSummary(
        database_path=Path(database_filename),
        wallpaper_count=wallpaper_count,
        visible_wallpaper_count=visible_count,
        localization_count=len(localization_rows),
        image_resource_count=len(resource_rows),
        wallpaper_tag_count=len(wallpaper_tag_rows),
        tag_count=len(tag_rows),
        date_from=start_date,
        date_to=end_date,
    )


def run_benchmarks(
    *,
    summary: DatasetSummary,
    public_service: PublicCatalogService,
    admin_service: AdminContentService,
    warmup: int,
    iterations: int,
) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    public_scenarios = build_public_scenarios(summary)
    admin_scenarios = build_admin_scenarios(summary)

    for scenario in public_scenarios:
        results.append(
            benchmark_public_scenario(
                public_service=public_service,
                scenario=scenario,
                warmup=warmup,
                iterations=iterations,
            )
        )

    for scenario in admin_scenarios:
        results.append(
            benchmark_admin_scenario(
                admin_service=admin_service,
                scenario=scenario,
                warmup=warmup,
                iterations=iterations,
            )
        )

    return results


def build_public_scenarios(summary: DatasetSummary) -> tuple[PublicScenario, ...]:
    end_date = summary.date_to
    return (
        PublicScenario(
            name="public_keyword_like",
            description="公开列表关键词检索（标题/描述/本地化/标签）",
            threshold=ScenarioThreshold(p95_ms=80.0, p99_ms=140.0),
            queries=(
                PublicWallpaperListQuery(keyword="Aurora", page_size=DEFAULT_PAGE_SIZE),
                PublicWallpaperListQuery(keyword="Coast", page_size=DEFAULT_PAGE_SIZE),
                PublicWallpaperListQuery(keyword="Editorial", page_size=DEFAULT_PAGE_SIZE),
            ),
            keyword_sensitive=True,
        ),
        PublicScenario(
            name="public_tag_combo",
            description="公开列表双标签同时命中过滤",
            threshold=ScenarioThreshold(p95_ms=70.0, p99_ms=120.0),
            queries=(
                PublicWallpaperListQuery(
                    tag_keys="aurora,season-winter",
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                PublicWallpaperListQuery(
                    tag_keys="coast,season-summer",
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                PublicWallpaperListQuery(
                    tag_keys="forest,collection-editorial",
                    page_size=DEFAULT_PAGE_SIZE,
                ),
            ),
        ),
        PublicScenario(
            name="public_date_window",
            description="公开列表日期范围过滤",
            threshold=ScenarioThreshold(p95_ms=35.0, p99_ms=60.0),
            queries=(
                PublicWallpaperListQuery(
                    date_from=end_date - timedelta(days=29),
                    date_to=end_date,
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                PublicWallpaperListQuery(
                    date_from=end_date - timedelta(days=89),
                    date_to=end_date - timedelta(days=30),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                PublicWallpaperListQuery(
                    date_from=end_date - timedelta(days=179),
                    date_to=end_date - timedelta(days=90),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
            ),
        ),
        PublicScenario(
            name="public_combined_filters",
            description="公开列表关键词 + 标签 + 日期组合过滤",
            threshold=ScenarioThreshold(p95_ms=90.0, p99_ms=160.0),
            queries=(
                PublicWallpaperListQuery(
                    keyword="Aurora",
                    tag_keys="aurora,season-winter",
                    date_from=end_date - timedelta(days=179),
                    date_to=end_date,
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                PublicWallpaperListQuery(
                    keyword="Coast",
                    tag_keys="coast,collection-spotlight",
                    date_from=end_date - timedelta(days=179),
                    date_to=end_date,
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                PublicWallpaperListQuery(
                    keyword="Forest",
                    tag_keys="forest,collection-editorial",
                    date_from=end_date - timedelta(days=179),
                    date_to=end_date,
                    page_size=DEFAULT_PAGE_SIZE,
                ),
            ),
            keyword_sensitive=True,
        ),
    )


def build_admin_scenarios(summary: DatasetSummary) -> tuple[AdminScenario, ...]:
    end_date = summary.date_to
    return (
        AdminScenario(
            name="admin_keyword_like",
            description="后台内容列表关键词检索",
            threshold=ScenarioThreshold(p95_ms=120.0, p99_ms=200.0),
            queries=(
                AdminWallpaperListQuery(keyword="Aurora", page_size=DEFAULT_PAGE_SIZE),
                AdminWallpaperListQuery(keyword="Coast", page_size=DEFAULT_PAGE_SIZE),
                AdminWallpaperListQuery(keyword="Spotlight", page_size=DEFAULT_PAGE_SIZE),
            ),
            keyword_sensitive=True,
        ),
        AdminScenario(
            name="admin_created_window",
            description="后台内容列表创建时间范围过滤",
            threshold=ScenarioThreshold(p95_ms=45.0, p99_ms=80.0),
            queries=(
                AdminWallpaperListQuery(
                    created_from_utc=datetime.combine(
                        end_date - timedelta(days=29),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    created_to_utc=datetime.combine(
                        end_date,
                        datetime.max.time(),
                        tzinfo=UTC,
                    ),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                AdminWallpaperListQuery(
                    created_from_utc=datetime.combine(
                        end_date - timedelta(days=89),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    created_to_utc=datetime.combine(
                        end_date - timedelta(days=30),
                        datetime.max.time(),
                        tzinfo=UTC,
                    ),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                AdminWallpaperListQuery(
                    created_from_utc=datetime.combine(
                        end_date - timedelta(days=179),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    created_to_utc=datetime.combine(
                        end_date - timedelta(days=90),
                        datetime.max.time(),
                        tzinfo=UTC,
                    ),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
            ),
        ),
        AdminScenario(
            name="admin_combined_filters",
            description="后台内容列表关键词 + 状态 + 市场 + 时间组合过滤",
            threshold=ScenarioThreshold(p95_ms=130.0, p99_ms=220.0),
            queries=(
                AdminWallpaperListQuery(
                    keyword="Editorial",
                    content_status="enabled",
                    market_code="en-US",
                    created_from_utc=datetime.combine(
                        end_date - timedelta(days=179),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    created_to_utc=datetime.combine(
                        end_date,
                        datetime.max.time(),
                        tzinfo=UTC,
                    ),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                AdminWallpaperListQuery(
                    keyword="Spotlight",
                    content_status="enabled",
                    market_code="fr-FR",
                    created_from_utc=datetime.combine(
                        end_date - timedelta(days=179),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    created_to_utc=datetime.combine(
                        end_date,
                        datetime.max.time(),
                        tzinfo=UTC,
                    ),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
                AdminWallpaperListQuery(
                    keyword="Editorial",
                    content_status="disabled",
                    market_code="de-DE",
                    created_from_utc=datetime.combine(
                        end_date - timedelta(days=179),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    created_to_utc=datetime.combine(
                        end_date,
                        datetime.max.time(),
                        tzinfo=UTC,
                    ),
                    page_size=DEFAULT_PAGE_SIZE,
                ),
            ),
            keyword_sensitive=True,
        ),
    )


def benchmark_public_scenario(
    *,
    public_service: PublicCatalogService,
    scenario: PublicScenario,
    warmup: int,
    iterations: int,
) -> BenchmarkResult:
    totals = []
    samples_ms: list[float] = []
    for run_index in range(warmup + iterations):
        query = scenario.queries[run_index % len(scenario.queries)]
        started = time.perf_counter()
        _, pagination = public_service.list_wallpapers(
            query=query,
            default_market_code=DEFAULT_MARKET_CODE,
            accept_language=DEFAULT_ACCEPT_LANGUAGE,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if pagination.total < 1:
            raise RuntimeError(f"Scenario {scenario.name} returned no rows.")
        if run_index >= warmup:
            totals.append(pagination.total)
            samples_ms.append(elapsed_ms)
    return build_result(
        category="public",
        name=scenario.name,
        description=scenario.description,
        totals=totals,
        samples_ms=samples_ms,
        threshold=scenario.threshold,
        keyword_sensitive=scenario.keyword_sensitive,
    )


def benchmark_admin_scenario(
    *,
    admin_service: AdminContentService,
    scenario: AdminScenario,
    warmup: int,
    iterations: int,
) -> BenchmarkResult:
    totals = []
    samples_ms: list[float] = []
    for run_index in range(warmup + iterations):
        query = scenario.queries[run_index % len(scenario.queries)]
        started = time.perf_counter()
        _, pagination = admin_service.list_wallpapers(query=query)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if pagination.total < 1:
            raise RuntimeError(f"Scenario {scenario.name} returned no rows.")
        if run_index >= warmup:
            totals.append(pagination.total)
            samples_ms.append(elapsed_ms)
    return build_result(
        category="admin",
        name=scenario.name,
        description=scenario.description,
        totals=totals,
        samples_ms=samples_ms,
        threshold=scenario.threshold,
        keyword_sensitive=scenario.keyword_sensitive,
    )


def build_result(
    *,
    category: str,
    name: str,
    description: str,
    totals: list[int],
    samples_ms: list[float],
    threshold: ScenarioThreshold,
    keyword_sensitive: bool,
) -> BenchmarkResult:
    if not samples_ms:
        raise RuntimeError(f"Scenario {name} did not produce any measured samples.")
    sorted_samples = sorted(samples_ms)
    p50_ms = percentile(sorted_samples, 50)
    p95_ms = percentile(sorted_samples, 95)
    p99_ms = percentile(sorted_samples, 99)
    evaluation = "PASS" if p95_ms <= threshold.p95_ms and p99_ms <= threshold.p99_ms else "REVIEW"
    return BenchmarkResult(
        category=category,
        name=name,
        description=description,
        runs=len(samples_ms),
        total_hits_preview=format_totals_preview(totals),
        p50_ms=p50_ms,
        p95_ms=p95_ms,
        p99_ms=p99_ms,
        max_ms=max(sorted_samples),
        threshold=threshold,
        evaluation=evaluation,
        keyword_sensitive=keyword_sensitive,
    )


def print_report(
    *,
    summary: DatasetSummary,
    results: list[BenchmarkResult],
    total_elapsed_ms: float,
) -> None:
    keyword_results = [result for result in results if result.keyword_sensitive]
    fts_recommended = any(result.evaluation == "REVIEW" for result in keyword_results)

    print("BingWall Query Benchmark")
    print(f"Generated at (UTC): {isoformat_utc(utc_now())}")
    print(
        "Dataset: "
        f"wallpapers={summary.wallpaper_count}, "
        f"visible={summary.visible_wallpaper_count}, "
        f"localizations={summary.localization_count}, "
        f"image_resources={summary.image_resource_count}, "
        f"wallpaper_tags={summary.wallpaper_tag_count}, "
        f"tags={summary.tag_count}"
    )
    print(f"Date span: {summary.date_from.isoformat()} -> {summary.date_to.isoformat()}")
    print(
        "Runtime: "
        f"python={sys.version.split()[0]}, "
        f"sqlite={sqlite3.sqlite_version}, "
        f"total_elapsed_ms={total_elapsed_ms:.1f}"
    )
    print()
    print(
        "category | scenario | runs | total_hits | p50_ms | p95_ms | p99_ms | "
        "max_ms | threshold | evaluation"
    )
    print("-" * 132)
    for result in results:
        print(
            f"{result.category:<8} | "
            f"{result.name:<23} | "
            f"{result.runs:>4} | "
            f"{result.total_hits_preview:<12} | "
            f"{result.p50_ms:>6.1f} | "
            f"{result.p95_ms:>6.1f} | "
            f"{result.p99_ms:>6.1f} | "
            f"{result.max_ms:>6.1f} | "
            f"p95<={result.threshold.p95_ms:.0f}/p99<={result.threshold.p99_ms:.0f} | "
            f"{result.evaluation}"
        )
    print()
    print("Upgrade policy")
    print("- Keep current LIKE strategy while all keyword scenarios remain within threshold.")
    print(
        "- Review extra B-tree indexes first if pure date/time filters exceed threshold "
        "or regress by more than 2x against this baseline."
    )
    print(
        "- Review SQLite FTS when any keyword-sensitive scenario reaches REVIEW, "
        "or when the wallpaper table grows beyond roughly 50,000 rows."
    )
    print(f"- Current FTS recommendation: {'REVIEW' if fts_recommended else 'HOLD'}")


def percentile(sorted_values: list[float], target_percent: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot compute percentile of an empty sequence.")
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (len(sorted_values) - 1) * (target_percent / 100)
    lower_index = math.floor(rank)
    upper_index = math.ceil(rank)
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    if lower_index == upper_index:
        return lower
    weight = rank - lower_index
    return lower + (upper - lower) * weight


def format_totals_preview(totals: list[int]) -> str:
    unique_totals = sorted(set(totals))
    preview = ",".join(str(value) for value in unique_totals[:3])
    if len(unique_totals) > 3:
        preview = f"{preview},..."
    return preview


def utc_now() -> datetime:
    return datetime.now(tz=UTC).replace(microsecond=0)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    normalized = []
    for character in value.lower():
        if character.isalnum():
            normalized.append(character)
        elif character in {" ", "-", "_"}:
            normalized.append("-")
    return "".join(normalized).strip("-")


if __name__ == "__main__":
    raise SystemExit(main())
