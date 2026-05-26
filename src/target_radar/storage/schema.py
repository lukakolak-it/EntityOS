"""SQLite schema for the local MVP database."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from target_radar.use_cases import DEFAULT_USE_CASES


SCHEMA_VERSION = 2

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    preset TEXT NOT NULL,
    draft_language TEXT NOT NULL,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS use_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_from_template TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    use_case_id INTEGER REFERENCES use_cases(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    roles_json TEXT NOT NULL DEFAULT '[]',
    regions_json TEXT NOT NULL DEFAULT '[]',
    tech_keywords_json TEXT NOT NULL DEFAULT '[]',
    industry_keywords_json TEXT NOT NULL DEFAULT '[]',
    exclude_keywords_json TEXT NOT NULL DEFAULT '[]',
    attributes_json TEXT NOT NULL DEFAULT '{}',
    manual_query TEXT,
    draft_language TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_profile_id INTEGER NOT NULL REFERENCES search_profiles(id) ON DELETE CASCADE,
    use_case_id INTEGER REFERENCES use_cases(id) ON DELETE SET NULL,
    use_case_version INTEGER,
    use_case_snapshot_json TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    phases_json TEXT NOT NULL DEFAULT '[]',
    request_budget INTEGER,
    results_per_query INTEGER,
    stats_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    base_url TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    query_template TEXT,
    template_set TEXT,
    query_score INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS serp_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_query_id INTEGER NOT NULL REFERENCES source_queries(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES targets(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    status TEXT NOT NULL,
    import_status TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS target_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    page_type TEXT NOT NULL DEFAULT 'other',
    http_status INTEGER,
    title TEXT,
    text TEXT,
    error_message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    fetched_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    page_id INTEGER REFERENCES target_pages(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL,
    text TEXT NOT NULL,
    context_type TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS target_status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    phase TEXT NOT NULL,
    reason TEXT,
    error_message TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS target_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    rule_score INTEGER,
    ai_score INTEGER,
    raw_confidence REAL,
    confidence REAL,
    recommended_action TEXT NOT NULL,
    rating_status TEXT NOT NULL,
    source_quality TEXT,
    rating_version TEXT NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    risks_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    input_snapshot_json TEXT NOT NULL DEFAULT '{}',
    error_type TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    score_id INTEGER REFERENCES target_scores(id) ON DELETE SET NULL,
    draft_type TEXT NOT NULL,
    draft_version TEXT NOT NULL,
    language TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    used_context_json TEXT NOT NULL DEFAULT '{}',
    regenerated_from_draft_id INTEGER REFERENCES action_drafts(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS local_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_profiles_profile_id
    ON search_profiles(profile_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_search_profile_id
    ON pipeline_runs(search_profile_id);
CREATE INDEX IF NOT EXISTS idx_targets_status
    ON targets(status);
CREATE INDEX IF NOT EXISTS idx_source_queries_pipeline_run_id
    ON source_queries(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_serp_results_source_query_id
    ON serp_results(source_query_id);
CREATE INDEX IF NOT EXISTS idx_serp_results_domain
    ON serp_results(domain);
CREATE INDEX IF NOT EXISTS idx_target_pages_target_id
    ON target_pages(target_id);
CREATE INDEX IF NOT EXISTS idx_evidence_target_id
    ON evidence(target_id);
CREATE INDEX IF NOT EXISTS idx_target_status_log_target_id
    ON target_status_log(target_id);
CREATE INDEX IF NOT EXISTS idx_target_status_log_pipeline_run_id
    ON target_status_log(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_target_scores_target_id
    ON target_scores(target_id);
CREATE INDEX IF NOT EXISTS idx_action_drafts_target_id
    ON action_drafts(target_id);
CREATE INDEX IF NOT EXISTS idx_local_operations_created_at
    ON local_operations(created_at);
"""


def init_db(connection: sqlite3.Connection) -> None:
    """Create all MVP tables and indexes if they do not exist."""

    current_version = schema_version(connection)
    _backup_database_before_migration(connection, current_version=current_version)
    connection.executescript(SCHEMA_SQL)
    _migrate_schema(connection)
    _seed_default_use_cases(connection)
    _backfill_default_use_case(connection)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row is not None else 0


def schema_status(connection: sqlite3.Connection) -> dict[str, object]:
    current_version = schema_version(connection)
    database_path = _database_path(connection)
    backup_dir = (
        str((Path(database_path).expanduser().resolve().parent / "backups"))
        if database_path
        else None
    )
    return {
        "current_version": current_version,
        "expected_version": SCHEMA_VERSION,
        "migration_status": (
            "current" if current_version == SCHEMA_VERSION else "needs_migration"
        ),
        "database_path": database_path,
        "backup_dir": backup_dir,
        "last_backup": _last_backup_path(database_path) if database_path else None,
    }


def _migrate_schema(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(
        connection,
        "search_profiles",
        "use_case_id",
        "INTEGER REFERENCES use_cases(id) ON DELETE SET NULL",
    )
    _add_column_if_missing(
        connection,
        "pipeline_runs",
        "use_case_id",
        "INTEGER REFERENCES use_cases(id) ON DELETE SET NULL",
    )
    _add_column_if_missing(connection, "pipeline_runs", "use_case_version", "INTEGER")
    _add_column_if_missing(connection, "pipeline_runs", "use_case_snapshot_json", "TEXT")
    _add_column_if_missing(
        connection,
        "search_profiles",
        "attributes_json",
        "TEXT NOT NULL DEFAULT '{}'",
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_search_profiles_use_case_id
            ON search_profiles(use_case_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_pipeline_runs_use_case_id
            ON pipeline_runs(use_case_id)
        """
    )


def _backup_database_before_migration(
    connection: sqlite3.Connection,
    *,
    current_version: int,
) -> str | None:
    if current_version >= SCHEMA_VERSION or not _has_existing_schema(connection):
        return None
    database_path = _database_path(connection)
    if not database_path:
        return None
    source_path = Path(database_path).expanduser().resolve()
    if not source_path.exists() or source_path.stat().st_size == 0:
        return None

    backup_dir = source_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    backup_path = (
        backup_dir
        / f"{source_path.stem}.schema-v{current_version}.{timestamp}{source_path.suffix}"
    )
    backup_connection = sqlite3.connect(backup_path)
    try:
        connection.backup(backup_connection)
    finally:
        backup_connection.close()
    return str(backup_path)


def _has_existing_schema(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def _database_path(connection: sqlite3.Connection) -> str | None:
    rows = connection.execute("PRAGMA database_list").fetchall()
    for row in rows:
        name = row[1] if not isinstance(row, sqlite3.Row) else row["name"]
        path = row[2] if not isinstance(row, sqlite3.Row) else row["file"]
        if name == "main" and path:
            return str(path)
    return None


def _last_backup_path(database_path: str) -> str | None:
    source_path = Path(database_path).expanduser().resolve()
    backup_dir = source_path.parent / "backups"
    if not backup_dir.exists():
        return None
    backups = sorted(
        backup_dir.glob(f"{source_path.stem}.schema-v*{source_path.suffix}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return str(backups[0]) if backups else None


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_spec: str,
) -> None:
    if column_name in _column_names(connection, table_name):
        return
    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_spec}")


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _seed_default_use_cases(connection: sqlite3.Connection) -> None:
    now = datetime.now(UTC).isoformat()
    for use_case in DEFAULT_USE_CASES:
        config_json = _json_dumps(use_case.to_dict())
        existing = connection.execute(
            "SELECT id, status FROM use_cases WHERE slug = ?",
            (use_case.id,),
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO use_cases (
                    slug, name, description, version, status, config_json,
                    created_from_template, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    use_case.id,
                    use_case.name,
                    use_case.description,
                    use_case.version,
                    use_case.status.value,
                    config_json,
                    use_case.created_from_template,
                    now,
                    now,
                ),
            )
            continue

        if existing[1] == "template":
            connection.execute(
                """
                UPDATE use_cases
                SET name = ?, description = ?, version = ?, status = ?,
                    config_json = ?, created_from_template = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    use_case.name,
                    use_case.description,
                    use_case.version,
                    use_case.status.value,
                    config_json,
                    use_case.created_from_template,
                    now,
                    existing[0],
                ),
            )


def _backfill_default_use_case(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT id FROM use_cases WHERE slug = ?",
        ("application_student",),
    ).fetchone()
    if row is None:
        return
    connection.execute(
        "UPDATE search_profiles SET use_case_id = ? WHERE use_case_id IS NULL",
        (row[0],),
    )


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
