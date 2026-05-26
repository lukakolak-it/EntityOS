"""Local diagnostics for Target Radar."""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from target_radar.config import AppConfig, load_app_config
from target_radar.config.settings import DEFAULT_ENV_FILE
from target_radar.ops.logging import redact_value
from target_radar.storage import SCHEMA_VERSION, SQLiteStore, schema_status, sqlite_path_from_url


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
    "local_operations",
)
MIN_PYTHON = (3, 11)


def collect_diagnostics(
    database_url: str,
    *,
    config: AppConfig | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
) -> dict[str, Any]:
    """Return a secret-safe snapshot useful for local debugging."""

    selected_config = config or load_app_config(env_file=env_file)
    checks: list[dict[str, Any]] = []
    table_counts: dict[str, int] = {}
    latest_runs: list[dict[str, Any]] = []
    latest_operations: list[dict[str, Any]] = []
    review_count = 0
    database_payload = _database_base_payload(database_url)

    _add_check(
        checks,
        key="python_version",
        label="Python",
        status="ok" if sys.version_info >= MIN_PYTHON else "error",
        message=f"{platform.python_version()} at {sys.executable}",
        next_step=None if sys.version_info >= MIN_PYTHON else "Install Python 3.11 or newer.",
    )

    for key, path in _filesystem_targets(database_url, selected_config).items():
        writable = _directory_writable(path)
        _add_check(
            checks,
            key=f"writable_{key}",
            label=f"Writable {key}",
            status="ok" if writable else "error",
            message=str(path),
            next_step=None if writable else f"Create or grant write access to {path}.",
        )

    try:
        store = SQLiteStore.open(database_url)
        try:
            table_counts = store.table_counts(CORE_TABLES)
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
            latest_operations = store.list_local_operations(limit=5)
            review_count = len(store.list_review_queue_items(limit=500))
            db_schema = schema_status(store.connection)
            database_payload.update(
                {
                    "status": "ok",
                    "schema": db_schema,
                    "schema_version": db_schema["current_version"],
                    "expected_schema_version": SCHEMA_VERSION,
                    "migration_status": db_schema["migration_status"],
                }
            )
            _add_check(
                checks,
                key="database_open",
                label="Database",
                status="ok",
                message=f"SQLite ready at {database_payload.get('path') or database_payload['url']}",
            )
            _add_check(
                checks,
                key="schema_version",
                label="Schema",
                status="ok" if db_schema["migration_status"] == "current" else "warning",
                message=f"{db_schema['current_version']} / {SCHEMA_VERSION}",
                next_step=(
                    None
                    if db_schema["migration_status"] == "current"
                    else "Run init-db or restart the local server to apply migrations."
                ),
            )
        finally:
            store.close()
    except Exception as exc:  # pragma: no cover - defensive diagnostics path
        database_payload.update({"status": "error", "error": str(exc)})
        _add_check(
            checks,
            key="database_open",
            label="Database",
            status="error",
            message=str(exc),
            next_step="Check DATABASE_URL and local write permissions.",
        )

    provider_payload = _provider_diagnostics(selected_config, checks)
    status = _overall_status(checks)
    return redact_value(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": status,
            "python": {
                "version": platform.python_version(),
                "executable": sys.executable,
                "minimum": ".".join(str(part) for part in MIN_PYTHON),
            },
            "host": {
                "platform": platform.platform(),
                "cwd": str(Path.cwd()),
                "env_file": str(env_file) if env_file is not None else None,
            },
            "database": database_payload,
            "filesystem": {
                key: {"path": str(path), "writable": _directory_writable(path)}
                for key, path in _filesystem_targets(database_url, selected_config).items()
            },
            "providers": provider_payload,
            "checks": checks,
            "table_counts": table_counts,
            "latest_runs": latest_runs,
            "latest_operations": latest_operations,
            "review_queue_count": review_count,
        }
    )


def _database_base_payload(database_url: str) -> dict[str, Any]:
    path = None
    exists = None
    if database_url == ":memory:" or database_url.startswith("sqlite"):
        try:
            raw_path = sqlite_path_from_url(database_url)
            if raw_path != ":memory:":
                path = str(Path(raw_path).expanduser().resolve())
                exists = Path(path).exists()
        except ValueError:
            path = None
    return {
        "status": "unknown",
        "url": redact_value({"database_url": database_url})["database_url"],
        "path": path,
        "exists": exists,
    }


def _filesystem_targets(database_url: str, config: AppConfig) -> dict[str, Path]:
    targets = {
        "data": Path("data"),
        "logs": Path("logs"),
        "exports": Path("exports"),
    }
    if config.infrastructure.log_file:
        targets["log_file_parent"] = Path(config.infrastructure.log_file).parent
    try:
        db_path = sqlite_path_from_url(database_url)
        if db_path != ":memory:":
            targets["database_parent"] = Path(db_path).expanduser().resolve().parent
    except ValueError:
        pass
    return targets


def _directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".target-radar-write-", delete=True):
            return True
    except OSError:
        return False


def _provider_diagnostics(config: AppConfig, checks: list[dict[str, Any]]) -> dict[str, Any]:
    search_provider = config.search_provider.provider.strip().lower()
    brave_key_configured = bool(
        config.search_provider.brave_api_key or config.search_provider.search_engine_token
    )
    brave_status = "ok" if brave_key_configured else ("error" if search_provider == "brave" else "optional")
    _add_check(
        checks,
        key="brave_key",
        label="Brave",
        status=brave_status,
        message=(
            "Brave key configured"
            if brave_key_configured
            else "Brave key missing; mock search still works"
        ),
        next_step=(
            None
            if brave_key_configured or search_provider != "brave"
            else "Set BRAVE_API_KEY or switch SEARCH_PROVIDER to mock."
        ),
    )

    light_provider = config.llm.light_provider.strip().lower()
    ollama = _ollama_payload(config) if light_provider in {"ollama", "local"} else None
    if light_provider in {"ollama", "local"}:
        assert ollama is not None
        _add_check(
            checks,
            key="ollama_reachable",
            label="Ollama",
            status="ok" if ollama["reachable"] else "error",
            message=(
                f"Ollama reachable at {ollama['base_url']}"
                if ollama["reachable"]
                else f"Ollama not reachable at {ollama['base_url']}"
            ),
            next_step=None if ollama["reachable"] else "Start Ollama or adjust LOCAL_AI_BASE_URL.",
        )
        _add_check(
            checks,
            key="ollama_light_model",
            label="Light model",
            status=(
                "ok"
                if ollama["model_available"]
                else ("error" if ollama["reachable"] else "skipped")
            ),
            message=f"{config.llm.light_model}",
            next_step=(
                None
                if ollama["model_available"] or not ollama["reachable"]
                else f"Run: ollama pull {config.llm.light_model}"
            ),
        )

    openai_ready = bool(config.llm.openai_api_key)
    return {
        "search": {
            "configured_provider": search_provider,
            "mock_ready": True,
            "brave_configured": brave_key_configured,
            "brave_ready": brave_key_configured,
            "configured_ready": (
                search_provider in {"mock", "fake"}
                or (search_provider == "brave" and brave_key_configured)
            ),
        },
        "llm": {
            "light": {
                "provider": light_provider,
                "model": config.llm.light_model,
                "configured": _llm_configured(config, light_provider),
                "ollama": ollama,
            },
            "heavy": {
                "provider": config.llm.heavy_provider,
                "model": config.llm.heavy_model,
                "configured": _llm_configured(config, config.llm.heavy_provider),
                "openai_key_configured": openai_ready,
                "enabled_in_ui": False,
            },
        },
    }


def _llm_configured(config: AppConfig, provider: str) -> bool:
    selected = provider.strip().lower()
    if selected in {"fake", "mock", "ollama", "local"}:
        return True
    if selected == "openai":
        return bool(config.llm.openai_api_key)
    return False


def _ollama_payload(config: AppConfig) -> dict[str, Any]:
    base_url = config.llm.local_base_url.rstrip("/")
    request = urllib.request.Request(f"{base_url}/api/tags")
    try:
        with urllib.request.urlopen(request, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("models")
        if not isinstance(models, list):
            models = []
        names = sorted(
            str(item.get("name") or item.get("model") or "").strip()
            for item in models
            if isinstance(item, dict)
        )
        names = [name for name in names if name]
        return {
            "base_url": base_url,
            "reachable": True,
            "models": names,
            "configured_model": config.llm.light_model,
            "model_available": config.llm.light_model in names if names else False,
        }
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "base_url": base_url,
            "reachable": False,
            "models": [],
            "configured_model": config.llm.light_model,
            "model_available": False,
            "error": str(exc),
        }


def _add_check(
    checks: list[dict[str, Any]],
    *,
    key: str,
    label: str,
    status: str,
    message: str,
    next_step: str | None = None,
) -> None:
    checks.append(
        {
            "key": key,
            "label": label,
            "status": status,
            "message": message,
            "next_step": next_step,
        }
    )


def _overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(check["status"]) for check in checks}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"
