"""Local diagnostics for Target Radar."""

from __future__ import annotations

from typing import Any

from target_radar.ops.logging import redact_value
from target_radar.storage import SQLiteStore


CORE_TABLES = (
    "profiles",
    "search_profiles",
    "pipeline_runs",
    "targets",
    "source_queries",
    "serp_results",
    "target_pages",
    "evidence",
    "target_status_log",
    "target_scores",
    "action_drafts",
)


def collect_diagnostics(database_url: str) -> dict[str, Any]:
    """Return a secret-safe snapshot useful for local debugging."""

    store = SQLiteStore.open(database_url)
    try:
        table_counts = {
            table: _count_table(store, table)
            for table in CORE_TABLES
        }
        latest_runs = [
            {
                "id": run.id,
                "status": run.status.value,
                "mode": run.mode,
                "created_at": run.created_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "error": run.error_message,
            }
            for run in store.list_pipeline_runs(limit=5)
        ]
        review_count = len(store.list_review_queue_items(limit=500))
        return {
            "database": {
                "status": "ok",
                "url": redact_value({"database_url": database_url})["database_url"],
            },
            "table_counts": table_counts,
            "latest_runs": latest_runs,
            "review_queue_count": review_count,
        }
    finally:
        store.close()


def _count_table(store: SQLiteStore, table: str) -> int:
    row = store.connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
    return int(row["count"])
