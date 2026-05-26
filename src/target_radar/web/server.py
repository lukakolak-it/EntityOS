"""Local-only HTTP server for the Target Radar UI."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from target_radar.config import AppConfig, load_app_config
from target_radar.config.settings import DEFAULT_ENV_FILE, load_dotenv
from target_radar.domain import (
    PipelinePhase,
    Profile,
    SearchProfile,
    Target,
    TargetStatus,
    domain_from_url,
    normalize_domain,
)
from target_radar.engines.evidence import EvidenceEngine
from target_radar.engines.draft import DraftEngine
from target_radar.engines.lead import FakeLeadEngine, LeadEngineConfig, create_lead_engine
from target_radar.engines.lead.query import QueryBuilder
from target_radar.engines.rating import (
    FakeAIRatingProvider,
    RatingEngine,
    create_rating_engine,
)
from target_radar.ops import collect_diagnostics
from target_radar.pipeline import (
    FetchConfig as PipelineFetchConfig,
    GeneratedFakeFetcher,
    HtmlExtractor,
    HttpFetcher,
    PipelineExecutionError,
    PipelineOrchestrator,
    PipelineRunRequest,
)
from target_radar.pipeline.importer import TargetImporter
from target_radar.storage import NotFoundError, SQLiteStore
from target_radar.use_cases import UseCaseConfig, UseCaseStatus, validate_use_case_config


STATIC_DIR = Path(__file__).with_name("static")
LOCAL_EXPORT_DIR = Path("exports")
LOGGER = logging.getLogger(__name__)
FULL_PIPELINE_PHASES = (
    PipelinePhase.LEAD,
    PipelinePhase.IMPORT,
    PipelinePhase.FETCH,
    PipelinePhase.EXTRACT,
    PipelinePhase.RATING,
    PipelinePhase.DRAFT,
)

LOCAL_SETTING_FIELDS: tuple[dict[str, Any], ...] = (
    {
        "group": "Local UI",
        "key": "TARGET_RADAR_ENV",
        "label": "Environment",
        "options": ("local", "dev", "test"),
    },
    {"group": "Local UI", "key": "LOG_LEVEL", "label": "Log Level", "options": ("DEBUG", "INFO", "WARNING", "ERROR")},
    {"group": "Local UI", "key": "DATABASE_URL", "label": "Database URL"},
    {"group": "Local UI", "key": "TARGET_RADAR_HOST", "label": "Host"},
    {"group": "Local UI", "key": "TARGET_RADAR_PORT", "label": "Port"},
    {"group": "Local UI", "key": "LOG_FILE", "label": "Log File"},
    {"group": "GitHub", "key": "GITHUB_TOKEN", "label": "GitHub Token", "secret": True},
    {"group": "GitHub", "key": "GITHUB_OWNER", "label": "Owner"},
    {"group": "GitHub", "key": "GITHUB_REPO", "label": "Repository"},
    {
        "group": "Search",
        "key": "SEARCH_PROVIDER",
        "label": "Search Provider",
        "options": ("mock", "brave", "searxng", "serpapi", "google"),
    },
    {"group": "Search", "key": "SEARCH_ENGINE_TOKEN", "label": "Search Engine Token", "secret": True},
    {"group": "Search", "key": "BRAVE_API_KEY", "label": "Brave API Key", "secret": True},
    {"group": "Search", "key": "SERPAPI_API_KEY", "label": "SerpApi Key", "secret": True},
    {"group": "Search", "key": "GOOGLE_CSE_API_KEY", "label": "Google CSE Key", "secret": True},
    {"group": "Search", "key": "GOOGLE_CSE_ID", "label": "Google CSE ID"},
    {"group": "Search", "key": "SEARXNG_BASE_URL", "label": "SearXNG Base URL"},
    {"group": "LLM", "key": "LLM_PROVIDER", "label": "Default Provider", "options": ("local", "ollama", "openai", "fake")},
    {"group": "LLM", "key": "LLM_MODEL", "label": "Default Model"},
    {"group": "LLM", "key": "LLM_LIGHT_PROVIDER", "label": "Light Provider", "options": ("ollama", "local", "openai", "fake")},
    {"group": "LLM", "key": "LLM_LIGHT_MODEL", "label": "Light Model"},
    {"group": "LLM", "key": "LLM_HEAVY_PROVIDER", "label": "Heavy Provider", "options": ("openai", "ollama", "local", "fake")},
    {"group": "LLM", "key": "LLM_HEAVY_MODEL", "label": "Heavy Model"},
    {"group": "LLM", "key": "OPENAI_API_KEY", "label": "OpenAI API Key", "secret": True},
    {"group": "LLM", "key": "OPENAI_BASE_URL", "label": "OpenAI Base URL"},
    {"group": "LLM", "key": "OPENAI_MODEL", "label": "OpenAI Model"},
    {"group": "LLM", "key": "ANTHROPIC_API_KEY", "label": "Anthropic API Key", "secret": True},
    {"group": "LLM", "key": "ANTHROPIC_MODEL", "label": "Anthropic Model"},
    {"group": "LLM", "key": "GEMINI_API_KEY", "label": "Gemini API Key", "secret": True},
    {"group": "LLM", "key": "GEMINI_MODEL", "label": "Gemini Model"},
    {"group": "LLM", "key": "MISTRAL_API_KEY", "label": "Mistral API Key", "secret": True},
    {"group": "LLM", "key": "MISTRAL_MODEL", "label": "Mistral Model"},
    {"group": "Local AI", "key": "LOCAL_AI_PROVIDER", "label": "Local Provider", "options": ("ollama", "local", "openai-compatible")},
    {"group": "Local AI", "key": "LOCAL_AI_BASE_URL", "label": "Local Base URL"},
    {"group": "Local AI", "key": "LOCAL_AI_OPENAI_BASE_URL", "label": "Local OpenAI Base URL"},
    {"group": "Local AI", "key": "LOCAL_AI_MODEL", "label": "Local Model"},
    {"group": "Local AI", "key": "LOCAL_AI_API_KEY", "label": "Local API Key", "secret": True},
    {"group": "Pipeline", "key": "TARGET_RADAR_REQUEST_BUDGET", "label": "Request Budget"},
    {"group": "Pipeline", "key": "TARGET_RADAR_RESULTS_PER_QUERY", "label": "Results per Query"},
    {"group": "Pipeline", "key": "TARGET_RADAR_MAX_RAW_RESULTS", "label": "Max Raw Results"},
    {"group": "Pipeline", "key": "TARGET_RADAR_DEFAULT_PROVIDER", "label": "Default Provider", "options": ("mock", "brave")},
    {"group": "Pipeline", "key": "TARGET_RADAR_SOURCE_BLOCK_THRESHOLD", "label": "Source Block Threshold"},
    {"group": "Pipeline", "key": "TARGET_RADAR_BLOCKED_SOURCE_DOMAINS", "label": "Blocked Source Domains"},
    {"group": "Rating", "key": "TARGET_RADAR_MIN_RULE_SCORE_FOR_AI", "label": "Min Rule Score for AI"},
    {"group": "Rating", "key": "TARGET_RADAR_MIN_AI_SCORE_FOR_REVIEW", "label": "Min AI Score for Review"},
    {"group": "Rating", "key": "TARGET_RADAR_MIN_AI_SCORE_FOR_DRAFT", "label": "Min AI Score for Draft"},
    {"group": "Rating", "key": "TARGET_RADAR_MIN_CONFIDENCE_FOR_DRAFT", "label": "Min Confidence for Draft"},
    {"group": "Rating", "key": "TARGET_RADAR_HARD_STOP_ACTION", "label": "Hard Stop Action", "options": ("skip", "review", "draft")},
    {"group": "Fetch", "key": "TARGET_RADAR_FETCH_TIMEOUT_SECONDS", "label": "Timeout Seconds"},
    {"group": "Fetch", "key": "TARGET_RADAR_MAX_PAGES_PER_TARGET", "label": "Max Pages per Target"},
    {"group": "Fetch", "key": "TARGET_RADAR_USER_AGENT", "label": "User Agent"},
    {"group": "Review", "key": "TARGET_RADAR_REVIEW_PAGE_SIZE", "label": "Page Size"},
    {"group": "Review", "key": "TARGET_RADAR_REVIEW_MAX_PAGE_SIZE", "label": "Max Page Size"},
    {"group": "Draft", "key": "TARGET_RADAR_DRAFT_LANGUAGE", "label": "Draft Language"},
    {"group": "Draft", "key": "TARGET_RADAR_DRAFT_TYPE", "label": "Draft Type"},
    {"group": "Draft", "key": "TARGET_RADAR_DRAFT_MAX_BODY_CHARS", "label": "Max Body Chars"},
)


class UseCaseImportConflict(ValueError):
    """Raised when an imported use case collides with an existing slug."""


def serve(
    *,
    database_url: str,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Run the local web server until interrupted."""

    server = create_server(database_url=database_url, host=host, port=port)
    LOGGER.info(
        "local web server started",
        extra={"extra": {"host": host, "port": port}},
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        LOGGER.info("local web server stopped")


def create_server(
    *,
    database_url: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    app_config: AppConfig | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
) -> ThreadingHTTPServer:
    handler = _make_handler(database_url, app_config=app_config, env_file=env_file)
    return ThreadingHTTPServer((host, port), handler)


def _make_handler(
    database_url: str,
    *,
    app_config: AppConfig | None = None,
    env_file: str | Path | None = DEFAULT_ENV_FILE,
):
    base_config = app_config or load_app_config(env_file=env_file)

    class TargetRadarHandler(BaseHTTPRequestHandler):
        server_version = "TargetRadarLocal/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path in {"", "/"}:
                    self._send_static("index.html")
                elif parsed.path.startswith("/static/"):
                    self._send_static(parsed.path.removeprefix("/static/"))
                elif parsed.path == "/api/health":
                    self._send_json({"status": "ok", "host": "127.0.0.1"})
                elif parsed.path == "/api/provider-status":
                    self._handle_provider_status()
                elif parsed.path == "/api/preflight":
                    self._handle_preflight()
                elif parsed.path == "/api/local-settings":
                    self._handle_local_settings()
                elif parsed.path == "/api/domain-policies":
                    self._handle_domain_policies()
                elif parsed.path == "/api/use-cases":
                    self._handle_use_cases()
                elif parsed.path.startswith("/api/use-cases/"):
                    self._handle_use_case_detail(parsed.path)
                elif parsed.path == "/api/search-profiles":
                    self._handle_search_profiles(parsed.query)
                elif parsed.path == "/api/context-sources":
                    self._handle_context_sources(parsed.query)
                elif parsed.path == "/api/review-queue":
                    self._handle_review_queue(parsed.query)
                elif parsed.path == "/api/pipeline-runs":
                    self._handle_pipeline_runs(parsed.query)
                elif parsed.path.startswith("/api/targets/"):
                    self._handle_target_detail(parsed.path)
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "not found")
            except NotFoundError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/pipeline-runs/fake":
                    self._handle_fake_run()
                elif parsed.path == "/api/pipeline-runs":
                    self._handle_pipeline_run_start()
                elif parsed.path == "/api/run-preview":
                    self._handle_run_preview()
                elif parsed.path == "/api/local-settings":
                    self._handle_local_settings_save()
                elif parsed.path == "/api/local-data/export":
                    self._handle_local_data_export()
                elif parsed.path == "/api/local-data/clear-run-data":
                    self._handle_local_data_clear()
                elif parsed.path == "/api/search-profiles":
                    self._handle_search_profile_create()
                elif parsed.path == "/api/domain-policies/blacklist":
                    self._handle_domain_blacklist()
                elif parsed.path == "/api/domain-policies/unblock":
                    self._handle_domain_unblock()
                elif parsed.path == "/api/use-cases/import":
                    self._handle_use_case_import()
                elif parsed.path.startswith("/api/use-cases/"):
                    self._handle_use_case_action(parsed.path)
                elif parsed.path.startswith("/api/targets/"):
                    self._handle_target_action(parsed.path)
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "not found")
            except NotFoundError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

        def do_PATCH(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path.startswith("/api/use-cases/"):
                    self._handle_use_case_patch(parsed.path)
                elif parsed.path.startswith("/api/drafts/"):
                    self._handle_draft_patch(parsed.path)
                elif parsed.path.startswith("/api/search-profiles/"):
                    self._handle_search_profile_patch(parsed.path)
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "not found")
            except NotFoundError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

        def do_DELETE(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path.startswith("/api/search-profiles/"):
                    self._handle_search_profile_delete(parsed.path)
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "not found")
            except NotFoundError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _store(self) -> SQLiteStore:
            return SQLiteStore.open(database_url)

        def _config(self) -> AppConfig:
            try:
                return load_app_config(env_file=env_file)
            except Exception:
                LOGGER.warning("failed to reload app config; using server startup config")
                return base_config

        def _handle_provider_status(self) -> None:
            self._send_json(_provider_status_payload(self._config(), database_url))

        def _handle_preflight(self) -> None:
            self._send_json(
                collect_diagnostics(
                    database_url,
                    config=self._config(),
                    env_file=env_file,
                )
            )

        def _handle_local_settings(self) -> None:
            self._send_json(_local_settings_payload(self._config(), env_file=env_file))

        def _handle_local_settings_save(self) -> None:
            payload = self._read_json(default={})
            values = payload.get("values")
            if not isinstance(values, dict):
                raise ValueError("values must be an object")
            updates = _local_setting_updates(values)
            if updates:
                _validate_local_setting_updates(env_file, updates)
                _update_env_file_values(env_file, updates)
            self._send_json(_local_settings_payload(self._config(), env_file=env_file))

        def _handle_local_data_export(self) -> None:
            store = self._store()
            try:
                payload = _write_local_data_export(store)
                self._send_json(payload)
            finally:
                store.close()

        def _handle_local_data_clear(self) -> None:
            store = self._store()
            try:
                export_payload = _write_local_data_export(store)
                clear_payload = store.clear_run_data(
                    export_path=str(export_payload["output_path"])
                )
                self._send_json({"export": export_payload, "clear": clear_payload})
            finally:
                store.close()

        def _handle_domain_policies(self) -> None:
            store = self._store()
            try:
                self._send_json(_domain_policy_payload(store))
            finally:
                store.close()

        def _handle_review_queue(self, query: str) -> None:
            params = parse_qs(query)
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])
            raw_use_case_id = params.get("use_case_id", [None])[0]
            use_case_id = int(raw_use_case_id) if raw_use_case_id else None
            store = self._store()
            try:
                self._send_json(
                    {
                        "items": store.list_review_queue_items(
                            limit=limit,
                            offset=offset,
                            use_case_id=use_case_id,
                        )
                    }
                )
            finally:
                store.close()

        def _handle_use_cases(self) -> None:
            store = self._store()
            try:
                use_cases = [
                    _use_case_payload(store, use_case)
                    for use_case in store.list_use_cases()
                ]
                self._send_json({"use_cases": use_cases})
            finally:
                store.close()

        def _handle_use_case_detail(self, path: str) -> None:
            slug, action = _parse_use_case_path(path)
            if action == "export":
                store = self._store()
                try:
                    use_case = store.get_use_case_by_slug(slug)
                    self._send_json(_use_case_export_payload(use_case))
                finally:
                    store.close()
                return
            if action is not None:
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "use POST for actions")
                return

            store = self._store()
            try:
                self._send_json(
                    {"use_case": _use_case_payload(store, store.get_use_case_by_slug(slug))}
                )
            finally:
                store.close()

        def _handle_use_case_action(self, path: str) -> None:
            slug, action = _parse_use_case_path(path)
            if action != "clone":
                self._send_error(HTTPStatus.NOT_FOUND, "unknown use case action")
                return

            payload = self._read_json(default={})
            store = self._store()
            try:
                source = store.get_use_case_by_slug(slug)
                cloned = _clone_use_case(
                    store,
                    source,
                    name=payload.get("name"),
                    slug=payload.get("slug"),
                )
                self._send_json(
                    {"use_case": _use_case_payload(store, cloned)},
                    status=HTTPStatus.CREATED,
                )
            finally:
                store.close()

        def _handle_use_case_import(self) -> None:
            payload = self._read_json(default={})
            conflict = str(payload.get("conflict") or "reject").strip().lower()
            config = _import_config_from_payload(payload)
            store = self._store()
            try:
                imported, import_status = _import_use_case(store, config, conflict=conflict)
                self._send_json(
                    {
                        "import_status": import_status,
                        "use_case": _use_case_payload(store, imported),
                    },
                    status=(
                        HTTPStatus.OK
                        if import_status == "overwritten"
                        else HTTPStatus.CREATED
                    ),
                )
            except UseCaseImportConflict as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.CONFLICT)
            finally:
                store.close()

        def _handle_search_profiles(self, query: str) -> None:
            params = parse_qs(query)
            limit = int(params.get("limit", ["50"])[0])
            store = self._store()
            try:
                self._send_json({"search_profiles": store.list_search_profiles(limit=limit)})
            finally:
                store.close()

        def _handle_context_sources(self, query: str) -> None:
            params = parse_qs(query)
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])
            pipeline_run_id = _optional_positive_int(
                params.get("pipeline_run_id", [None])[0]
            )
            search_profile_id = _optional_positive_int(
                params.get("search_profile_id", [None])[0]
            )
            use_case_id = _optional_positive_int(params.get("use_case_id", [None])[0])
            store = self._store()
            try:
                items = store.list_context_sources(
                    limit=limit,
                    offset=offset,
                    pipeline_run_id=pipeline_run_id,
                    search_profile_id=search_profile_id,
                    use_case_id=use_case_id,
                )
                self._send_json(
                    {
                        "context_sources": [_context_source_payload(item) for item in items],
                        "filters": {
                            "pipeline_run_id": pipeline_run_id,
                            "search_profile_id": search_profile_id,
                            "use_case_id": use_case_id,
                        },
                    }
                )
            finally:
                store.close()

        def _handle_search_profile_create(self) -> None:
            payload = self._read_json(default={})
            store = self._store()
            try:
                profile = store.create_profile(
                    Profile(
                        name=str(payload.get("profile_name") or "Local Profile"),
                        draft_language=str(payload.get("draft_language") or "de"),
                    )
                )
                search_profile = store.create_search_profile(
                    _search_profile_from_payload(
                        payload,
                        profile_id=profile.id,
                        default_name="Local Search",
                        store=store,
                    )
                )
                self._send_json(
                    {"search_profile": _search_profile_payload(search_profile)},
                    status=HTTPStatus.CREATED,
                )
            finally:
                store.close()

        def _handle_run_preview(self) -> None:
            payload = self._read_json(default={})
            store = self._store()
            try:
                self._send_json(_run_preview_payload(store, payload))
            finally:
                store.close()

        def _handle_domain_blacklist(self) -> None:
            payload = self._read_json(default={})
            domain = _domain_from_payload(payload)
            store = self._store()
            try:
                target = _blacklist_domain(store, domain)
                self._send_json({"target": _target_payload(target)})
            finally:
                store.close()

        def _handle_domain_unblock(self) -> None:
            payload = self._read_json(default={})
            domain = _domain_from_payload(payload)
            store = self._store()
            try:
                target = _unblock_domain(store, domain)
                self._send_json({"target": _target_payload(target)})
            finally:
                store.close()

        def _handle_use_case_patch(self, path: str) -> None:
            slug, action = _parse_use_case_path(path)
            if action is not None:
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "use PATCH on the use case")
                return

            payload = self._read_json(default={})
            config = payload.get("config") if "config" in payload else payload
            if not isinstance(config, dict):
                raise ValueError("config must be an object")
            next_config = dict(config)
            if next_config.get("id") not in {None, slug}:
                raise ValueError("use case id cannot be changed")
            next_config["id"] = slug

            store = self._store()
            try:
                existing = store.get_use_case_by_slug(slug)
                if _is_builtin_use_case(existing):
                    raise ValueError("built-in use case templates are read-only; clone before editing")
                updated = validate_use_case_config(next_config)
                store.save_use_case(updated)
                self._send_json(
                    {"use_case": _use_case_payload(store, store.get_use_case_by_slug(slug))}
                )
            finally:
                store.close()

        def _handle_pipeline_runs(self, query: str) -> None:
            params = parse_qs(query)
            limit = int(params.get("limit", ["20"])[0])
            store = self._store()
            try:
                self._send_json(
                    {"runs": [_pipeline_run_payload(run) for run in store.list_pipeline_runs(limit=limit)]}
                )
            finally:
                store.close()

        def _handle_target_detail(self, path: str) -> None:
            target_id, action = _parse_target_path(path)
            if action is not None:
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "use POST for actions")
                return

            store = self._store()
            try:
                target = store.get_target(target_id)
                payload = {
                    "target": _target_payload(target),
                    "pages": [_target_page_payload(page) for page in store.list_target_pages(target_id)],
                    "evidence": [_evidence_payload(item) for item in store.list_evidence(target_id)],
                    "ratings": [_rating_payload(item) for item in store.list_ratings(target_id)],
                    "drafts": [_draft_payload(item) for item in store.list_drafts(target_id)],
                    "status_logs": [_status_log_payload(item) for item in store.list_status_logs(target_id)],
                }
                self._send_json(payload)
            finally:
                store.close()

        def _handle_fake_run(self) -> None:
            payload = self._read_json(default={})
            payload["provider_mode"] = "fake"
            self._run_pipeline_from_payload(payload)

        def _handle_pipeline_run_start(self) -> None:
            self._run_pipeline_from_payload(self._read_json(default={}))

        def _run_pipeline_from_payload(self, payload: dict[str, Any]) -> None:
            provider_mode = _provider_mode(payload.get("provider_mode"))
            llm_mode = _llm_mode(payload.get("llm_mode"))
            fetch_mode = _fetch_mode(payload.get("fetch_mode"), provider_mode=provider_mode)
            phase_mode = _phase_mode(payload.get("phase_mode"))
            draft_enabled = _bool_payload(payload.get("draft_enabled"), default=True)
            phases = _phases_for_mode(phase_mode, draft_enabled=draft_enabled)
            request_budget = _positive_int(payload.get("request_budget"), default=10, maximum=100)
            results_per_query = _positive_int(payload.get("results_per_query"), default=5, maximum=20)
            max_pages_per_target = _positive_int(
                payload.get("max_pages_per_target"),
                default=2 if provider_mode == "fake" else self._config().fetch.max_pages_per_target,
                maximum=20,
            )
            store = self._store()
            try:
                profile, search_profile = _run_context(store, payload)
                orchestrator, search_provider = _orchestrator_for_run(
                    store=store,
                    profile=profile,
                    search_profile=search_profile,
                    config=self._config(),
                    provider_mode=provider_mode,
                    llm_mode=llm_mode,
                    fetch_mode=fetch_mode,
                    light_model=_optional_str(payload.get("light_model")),
                    request_budget=request_budget,
                    results_per_query=results_per_query,
                    max_pages_per_target=max_pages_per_target,
                )
                result = orchestrator.run(
                    PipelineRunRequest(
                        search_profile=search_profile,
                        mode=f"ui:{provider_mode}:{llm_mode}:{phase_mode}:{fetch_mode}",
                        phases=phases,
                        request_budget=request_budget,
                        results_per_query=results_per_query,
                    )
                )
                self._send_json(
                    _run_result_payload(
                        result,
                        provider_mode=provider_mode,
                        llm_mode=llm_mode,
                        fetch_mode=fetch_mode,
                        phase_mode=phase_mode,
                        search_provider=search_provider,
                    ),
                    status=HTTPStatus.CREATED,
                )
            except PipelineExecutionError as exc:
                self._send_json(
                    {
                        "run": _pipeline_run_payload(exc.run),
                        "provider_mode": provider_mode,
                        "llm_mode": llm_mode,
                        "fetch_mode": fetch_mode,
                        "phase_mode": phase_mode,
                        "error": str(exc),
                    },
                    status=HTTPStatus.CREATED,
                )
            finally:
                store.close()

        def _handle_target_action(self, path: str) -> None:
            target_id, action = _parse_target_path(path)
            if action is None:
                self._send_error(HTTPStatus.BAD_REQUEST, "missing action")
                return

            if action == "attach-context-source":
                payload = self._read_json(default={})
                context_source_id = _required_positive_int(
                    payload.get("context_source_id"),
                    "context_source_id",
                )
                store = self._store()
                try:
                    evidence = _attach_context_source_evidence(
                        store,
                        target_id=target_id,
                        context_source_id=context_source_id,
                    )
                    context_source = store.get_context_source(context_source_id)
                    self._send_json(
                        {
                            "evidence": _evidence_payload(evidence),
                            "context_source": _context_source_payload(context_source),
                        },
                        status=HTTPStatus.CREATED,
                    )
                finally:
                    store.close()
                return

            action_map = {
                "approve": TargetStatus.APPROVED,
                "reject": TargetStatus.REJECTED,
                "blacklist": TargetStatus.BLACKLISTED,
                "refetch": TargetStatus.FETCH_PENDING,
                "rerate": TargetStatus.RATING_PENDING,
                "regenerate-draft": TargetStatus.DRAFT_PENDING,
            }
            if action not in action_map:
                self._send_error(HTTPStatus.NOT_FOUND, "unknown target action")
                return

            store = self._store()
            try:
                if action in {"refetch", "rerate", "regenerate-draft"}:
                    profile, search_profile = _target_context(store, target_id)
                    store.set_target_status(
                        target_id,
                        action_map[action],
                        PipelinePhase.REPROCESS,
                        reason=f"ui action: {action}",
                        metadata={
                            "trigger": "ui_action",
                            "action": action,
                            "endpoint": f"POST /api/targets/{target_id}/{action}",
                        },
                    )
                    orchestrator = _fake_reprocess_orchestrator(
                        store=store,
                        profile=profile,
                        search_profile=search_profile,
                    )
                    if action == "refetch":
                        result = orchestrator.refetch_target(target_id, search_profile)
                    elif action == "rerate":
                        result = orchestrator.rerate_target(target_id, search_profile)
                    else:
                        result = orchestrator.regenerate_draft(target_id, search_profile)
                    self._send_json({"reprocess": _reprocess_result_payload(result)})
                    return

                log = store.set_target_status(
                    target_id,
                    action_map[action],
                    PipelinePhase.REVIEW if action in {"approve", "reject", "blacklist"} else PipelinePhase.REPROCESS,
                    reason=f"ui action: {action}",
                    metadata={"trigger": "ui_action", "action": action},
                )
                self._send_json({"status_log": _status_log_payload(log)})
            finally:
                store.close()

        def _handle_draft_patch(self, path: str) -> None:
            draft_id = _parse_id_path(path, "/api/drafts/")
            payload = self._read_json(default={})
            store = self._store()
            try:
                draft = store.update_draft(
                    draft_id,
                    subject=payload.get("subject"),
                    body=payload.get("body"),
                )
                self._send_json({"draft": _draft_payload(draft)})
            finally:
                store.close()

        def _handle_search_profile_patch(self, path: str) -> None:
            search_profile_id = _parse_id_path(path, "/api/search-profiles/")
            payload = self._read_json(default={})
            store = self._store()
            try:
                search_profile = store.update_search_profile(
                    search_profile_id,
                    profile_name=(
                        str(payload["profile_name"])
                        if payload.get("profile_name") is not None
                        else None
                    ),
                    name=str(payload["name"]) if payload.get("name") is not None else None,
                    use_case_id=(
                        int(payload["use_case_id"])
                        if payload.get("use_case_id") is not None
                        else None
                    ),
                    roles=_tuple_payload(payload.get("roles")) if "roles" in payload else None,
                    regions=(
                        _tuple_payload(payload.get("regions"))
                        if "regions" in payload
                        else None
                    ),
                    tech_keywords=(
                        _tuple_payload(payload.get("tech_keywords"))
                        if "tech_keywords" in payload
                        else None
                    ),
                    industry_keywords=(
                        _tuple_payload(payload.get("industry_keywords"))
                        if "industry_keywords" in payload
                        else None
                    ),
                    exclude_keywords=(
                        _tuple_payload(payload.get("exclude_keywords"))
                        if "exclude_keywords" in payload
                        else None
                    ),
                    attributes=(
                        dict(payload.get("attributes") or {})
                        if "attributes" in payload
                        else None
                    ),
                    manual_query=(
                        str(payload["manual_query"])
                        if payload.get("manual_query") is not None
                        else None
                    ),
                    draft_language=(
                        str(payload["draft_language"])
                        if payload.get("draft_language") is not None
                        else None
                    ),
                )
                self._send_json({"search_profile": _search_profile_payload(search_profile)})
            finally:
                store.close()

        def _handle_search_profile_delete(self, path: str) -> None:
            search_profile_id = _parse_id_path(path, "/api/search-profiles/")
            store = self._store()
            try:
                store.delete_search_profile(search_profile_id)
                self._send_json({"deleted": True, "search_profile_id": search_profile_id})
            finally:
                store.close()

        def _read_json(self, *, default: dict[str, Any]) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return default
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _send_static(self, name: str) -> None:
            safe_name = name.replace("\\", "/").lstrip("/")
            path = (STATIC_DIR / safe_name).resolve()
            if STATIC_DIR.resolve() not in path.parents and path != STATIC_DIR.resolve():
                self._send_error(HTTPStatus.FORBIDDEN, "invalid static path")
                return
            if not path.exists() or not path.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "static file not found")
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(
            self,
            payload: dict[str, Any],
            *,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            data = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            LOGGER.warning(
                "http error",
                extra={"extra": {"status": status.value, "path": self.path, "message": message}},
            )
            self._send_json({"error": message}, status=status)

    return TargetRadarHandler


def _local_settings_payload(
    config: AppConfig,
    *,
    env_file: str | Path | None,
) -> dict[str, Any]:
    env_values = load_dotenv(env_file) if env_file is not None else {}
    current_values = _local_setting_current_values(config)
    grouped: dict[str, list[dict[str, Any]]] = {}

    for field in LOCAL_SETTING_FIELDS:
        key = str(field["key"])
        is_secret = bool(field.get("secret"))
        configured = bool(
            _non_empty_value(env_values.get(key))
            or _non_empty_value(os.environ.get(key))
            or (is_secret and _non_empty_value(current_values.get(key)))
        )
        if key in env_values:
            source = ".env"
        elif key in os.environ:
            source = "process"
        else:
            source = "default"

        payload_field = {
            "key": key,
            "label": field["label"],
            "secret": is_secret,
            "configured": configured,
            "source": source,
            "value": "" if is_secret else str(current_values.get(key, "") or ""),
        }
        if "options" in field:
            payload_field["options"] = list(field["options"])
        grouped.setdefault(str(field["group"]), []).append(payload_field)

    return {
        "env_file": str(env_file) if env_file is not None else None,
        "groups": [
            {"name": group, "fields": fields}
            for group, fields in grouped.items()
        ],
    }


def _local_setting_current_values(config: AppConfig) -> dict[str, str | None]:
    return {
        "TARGET_RADAR_ENV": config.infrastructure.environment,
        "LOG_LEVEL": config.infrastructure.log_level,
        "DATABASE_URL": config.infrastructure.database_url,
        "TARGET_RADAR_HOST": config.infrastructure.host,
        "TARGET_RADAR_PORT": str(config.infrastructure.port),
        "LOG_FILE": config.infrastructure.log_file,
        "GITHUB_TOKEN": config.github.token,
        "GITHUB_OWNER": config.github.owner,
        "GITHUB_REPO": config.github.repo,
        "LLM_PROVIDER": config.llm.provider,
        "LLM_MODEL": config.llm.model,
        "LLM_HEAVY_PROVIDER": config.llm.heavy_provider,
        "LLM_HEAVY_MODEL": config.llm.heavy_model,
        "LLM_LIGHT_PROVIDER": config.llm.light_provider,
        "LLM_LIGHT_MODEL": config.llm.light_model,
        "OPENAI_API_KEY": config.llm.openai_api_key,
        "OPENAI_BASE_URL": config.llm.openai_base_url,
        "OPENAI_MODEL": config.llm.openai_model,
        "ANTHROPIC_API_KEY": config.llm.anthropic_api_key,
        "ANTHROPIC_MODEL": config.llm.anthropic_model,
        "GEMINI_API_KEY": config.llm.gemini_api_key,
        "GEMINI_MODEL": config.llm.gemini_model,
        "MISTRAL_API_KEY": config.llm.mistral_api_key,
        "MISTRAL_MODEL": config.llm.mistral_model,
        "LOCAL_AI_PROVIDER": config.llm.local_provider,
        "LOCAL_AI_BASE_URL": config.llm.local_base_url,
        "LOCAL_AI_OPENAI_BASE_URL": config.llm.local_openai_base_url,
        "LOCAL_AI_MODEL": config.llm.local_model,
        "LOCAL_AI_API_KEY": config.llm.local_api_key,
        "SEARCH_PROVIDER": config.search_provider.provider,
        "SEARCH_ENGINE_TOKEN": config.search_provider.search_engine_token,
        "BRAVE_API_KEY": config.search_provider.brave_api_key,
        "SERPAPI_API_KEY": config.search_provider.serpapi_api_key,
        "GOOGLE_CSE_API_KEY": config.search_provider.google_cse_api_key,
        "GOOGLE_CSE_ID": config.search_provider.google_cse_id,
        "SEARXNG_BASE_URL": config.search_provider.searxng_base_url,
        "TARGET_RADAR_REQUEST_BUDGET": str(config.lead_budget.request_budget),
        "TARGET_RADAR_RESULTS_PER_QUERY": str(config.lead_budget.results_per_query),
        "TARGET_RADAR_MAX_RAW_RESULTS": str(config.lead_budget.max_raw_results),
        "TARGET_RADAR_DEFAULT_PROVIDER": config.lead_budget.default_provider,
        "TARGET_RADAR_SOURCE_BLOCK_THRESHOLD": str(config.lead_budget.source_block_threshold),
        "TARGET_RADAR_BLOCKED_SOURCE_DOMAINS": ",".join(config.lead_budget.blocked_source_domains),
        "TARGET_RADAR_MIN_RULE_SCORE_FOR_AI": str(config.rating.min_rule_score_for_ai),
        "TARGET_RADAR_MIN_AI_SCORE_FOR_REVIEW": str(config.rating.min_ai_score_for_review),
        "TARGET_RADAR_MIN_AI_SCORE_FOR_DRAFT": str(config.rating.min_ai_score_for_draft),
        "TARGET_RADAR_MIN_CONFIDENCE_FOR_DRAFT": str(config.rating.min_confidence_for_draft),
        "TARGET_RADAR_HARD_STOP_ACTION": config.rating.hard_stop_action,
        "TARGET_RADAR_FETCH_TIMEOUT_SECONDS": str(config.fetch.timeout_seconds),
        "TARGET_RADAR_MAX_PAGES_PER_TARGET": str(config.fetch.max_pages_per_target),
        "TARGET_RADAR_USER_AGENT": config.fetch.user_agent,
        "TARGET_RADAR_REVIEW_PAGE_SIZE": str(config.review_queue.page_size),
        "TARGET_RADAR_REVIEW_MAX_PAGE_SIZE": str(config.review_queue.max_page_size),
        "TARGET_RADAR_DRAFT_LANGUAGE": config.draft.default_draft_language,
        "TARGET_RADAR_DRAFT_TYPE": config.draft.default_draft_type,
        "TARGET_RADAR_DRAFT_MAX_BODY_CHARS": str(config.draft.max_body_chars),
    }


def _local_setting_updates(values: dict[str, Any]) -> dict[str, str]:
    fields_by_key = {str(field["key"]): field for field in LOCAL_SETTING_FIELDS}
    updates: dict[str, str] = {}
    for key, raw_value in values.items():
        if key not in fields_by_key:
            raise ValueError(f"unknown local setting: {key}")
        value = str(raw_value or "").strip()
        if "\n" in value or "\r" in value:
            raise ValueError(f"local setting cannot contain newlines: {key}")
        if fields_by_key[key].get("secret") and not value:
            continue
        updates[key] = value
    return updates


def _update_env_file_values(
    env_file: str | Path | None,
    updates: dict[str, str],
) -> None:
    if env_file is None:
        raise ValueError("local settings env file is disabled")

    env_path = Path(env_file)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    rendered = {key: f"{key}={_format_env_value(value)}" for key, value in updates.items()}
    seen: set[str] = set()
    next_lines: list[str] = []

    for line in lines:
        key = _env_line_key(line)
        if key in rendered:
            next_lines.append(rendered[key])
            seen.add(key)
        else:
            next_lines.append(line)

    missing = [str(field["key"]) for field in LOCAL_SETTING_FIELDS if field["key"] in rendered and field["key"] not in seen]
    if missing and next_lines and next_lines[-1].strip():
        next_lines.append("")
    for key in missing:
        next_lines.append(rendered[key])

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def _validate_local_setting_updates(
    env_file: str | Path | None,
    updates: dict[str, str],
) -> None:
    values = dict(os.environ)
    if env_file is not None:
        values.update(load_dotenv(env_file))
    values.update(updates)
    load_app_config(env_file=None, environ=values)


def _env_line_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    key = stripped.split("=", 1)[0].strip()
    return key or None


def _format_env_value(value: str) -> str:
    if value == "":
        return ""
    should_quote = any(char.isspace() for char in value) or any(
        char in value for char in ('"', "'", "#", "=")
    )
    if not should_quote:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _non_empty_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _write_local_data_export(store: SQLiteStore) -> dict[str, Any]:
    payload = store.export_local_data()
    LOCAL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    output_path = LOCAL_EXPORT_DIR / f"target-radar-local-data-{timestamp}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    operation = store.record_local_operation(
        operation="export_local_data",
        status="completed",
        metadata={
            "output_path": str(output_path),
            "counts": payload["counts"],
            "secrets_included": False,
        },
    )
    return {
        "format": payload["format"],
        "generated_at": payload["generated_at"],
        "output_path": str(output_path),
        "secrets_included": False,
        "counts": payload["counts"],
        "operation": operation,
    }


def _parse_id_path(path: str, prefix: str) -> int:
    raw = path.removeprefix(prefix).strip("/")
    if "/" in raw or not raw:
        raise ValueError("invalid id path")
    return int(raw)


def _run_context(
    store: SQLiteStore,
    payload: dict[str, Any],
) -> tuple[Profile, SearchProfile]:
    search_profile_id = _optional_positive_int(payload.get("search_profile_id"))
    use_case_id = _optional_positive_int(payload.get("use_case_id"))
    if search_profile_id is not None:
        search_profile = store.get_search_profile(search_profile_id)
        if use_case_id is not None and use_case_id != search_profile.use_case_id:
            search_profile = store.update_search_profile_use_case(
                search_profile_id,
                use_case_id,
            )
        if _payload_has_search_values(payload):
            search_profile = SearchProfile(
                id=search_profile.id,
                profile_id=search_profile.profile_id,
                use_case_id=search_profile.use_case_id,
                name=search_profile.name,
                roles=(
                    _tuple_payload(payload.get("roles"))
                    if "roles" in payload
                    else search_profile.roles
                ),
                regions=(
                    _tuple_payload(payload.get("regions"))
                    if "regions" in payload
                    else search_profile.regions
                ),
                tech_keywords=(
                    _tuple_payload(payload.get("tech_keywords"))
                    if "tech_keywords" in payload
                    else search_profile.tech_keywords
                ),
                industry_keywords=(
                    _tuple_payload(payload.get("industry_keywords"))
                    if "industry_keywords" in payload
                    else search_profile.industry_keywords
                ),
                exclude_keywords=(
                    _tuple_payload(payload.get("exclude_keywords"))
                    if "exclude_keywords" in payload
                    else search_profile.exclude_keywords
                ),
                attributes=(
                    dict(payload.get("attributes") or {})
                    if "attributes" in payload
                    else search_profile.attributes
                ),
                manual_query=search_profile.manual_query,
                draft_language=search_profile.draft_language,
                created_at=search_profile.created_at,
            )
        profile = store.get_profile(search_profile.profile_id)
        return profile, search_profile

    profile = store.create_profile(
        Profile(name=str(payload.get("profile_name") or "Local Profile"))
    )
    search_profile = store.create_search_profile(
        _search_profile_from_payload(
            payload,
            profile_id=profile.id,
            default_name="Local Search",
            store=store,
        )
    )
    return profile, search_profile


def _payload_has_search_values(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in (
            "roles",
            "regions",
            "tech_keywords",
            "industry_keywords",
            "exclude_keywords",
            "attributes",
        )
    )


def _search_profile_from_payload(
    payload: dict[str, Any],
    *,
    profile_id: int,
    default_name: str,
    store: SQLiteStore | None = None,
) -> SearchProfile:
    use_case_id = _optional_positive_int(payload.get("use_case_id"))
    use_case = store.get_use_case(use_case_id) if store is not None and use_case_id else None
    default_roles = (
        ("Werkstudent IT",)
        if use_case is None or use_case.id == "application_student"
        else ()
    )
    default_regions = ("Essen",) if use_case is None else ()
    default_tech = ("Python",) if use_case is None or use_case.id == "application_student" else ()
    return SearchProfile(
        profile_id=profile_id,
        name=str(payload.get("search_name") or payload.get("name") or default_name),
        roles=_tuple_payload(payload.get("roles"), default=default_roles),
        regions=_tuple_payload(payload.get("regions"), default=default_regions),
        tech_keywords=_tuple_payload(payload.get("tech_keywords"), default=default_tech),
        industry_keywords=_tuple_payload(payload.get("industry_keywords")),
        exclude_keywords=_tuple_payload(payload.get("exclude_keywords")),
        manual_query=_optional_str(payload.get("manual_query")),
        draft_language=_optional_str(payload.get("draft_language")),
        use_case_id=use_case_id,
        attributes=dict(payload.get("attributes") or {}),
    )


def _orchestrator_for_run(
    *,
    store: SQLiteStore,
    profile: Profile,
    search_profile: SearchProfile,
    config: AppConfig,
    provider_mode: str,
    llm_mode: str,
    fetch_mode: str,
    light_model: str | None,
    request_budget: int,
    results_per_query: int,
    max_pages_per_target: int,
) -> tuple[PipelineOrchestrator, str]:
    selected_config = _config_with_light_model(config, light_model)
    importer = TargetImporter(
        store,
        blacklisted_domains=store.list_domains_by_status(TargetStatus.BLACKLISTED),
    )
    if provider_mode == "fake":
        rating_engine = (
            RatingEngine()
            if llm_mode == "off"
            else create_rating_engine(selected_config, task="light")
        )
        return (
            PipelineOrchestrator(
                store,
                FakeLeadEngine(),
                importer=importer,
                fetcher=_fetcher_for_mode(
                    fetch_mode,
                    config=selected_config,
                    search_profile=search_profile,
                ),
                extractor=HtmlExtractor(),
                rating_engine=rating_engine,
                draft_engine=DraftEngine(),
                profile=profile,
                max_pages_per_target=max_pages_per_target,
            ),
            "mock",
        )

    selected_config = _config_for_provider_mode(selected_config, provider_mode)
    lead_engine = create_lead_engine(selected_config, store=store)
    lead_engine.config = LeadEngineConfig(
        request_budget=request_budget,
        results_per_query=results_per_query,
        template_set=lead_engine.config.template_set,
        source_block_threshold=lead_engine.config.source_block_threshold,
    )
    fetcher = _fetcher_for_mode(
        fetch_mode,
        config=selected_config,
        search_profile=search_profile,
    )
    rating_engine = (
        RatingEngine()
        if llm_mode == "off"
        else create_rating_engine(selected_config, task="light")
    )
    return (
        PipelineOrchestrator(
            store,
            lead_engine,
            importer=importer,
            fetcher=fetcher,
            extractor=HtmlExtractor(),
            rating_engine=rating_engine,
            draft_engine=DraftEngine(),
            profile=profile,
            max_pages_per_target=max_pages_per_target,
        ),
        lead_engine.provider.name,
    )


def _config_for_provider_mode(config: AppConfig, provider_mode: str) -> AppConfig:
    if provider_mode == "configured":
        return config
    if provider_mode == "brave":
        return replace(
            config,
            search_provider=replace(config.search_provider, provider="brave"),
        )
    raise ValueError("provider_mode must be one of: fake, brave, configured")


def _config_with_light_model(config: AppConfig, light_model: str | None) -> AppConfig:
    if not light_model:
        return config
    return replace(config, llm=replace(config.llm, light_model=light_model))


def _fetcher_for_mode(
    fetch_mode: str,
    *,
    config: AppConfig,
    search_profile: SearchProfile,
):
    if fetch_mode == "fake":
        return GeneratedFakeFetcher(terms=_search_terms(search_profile))
    if fetch_mode == "http":
        return HttpFetcher(
            PipelineFetchConfig(
                timeout_seconds=config.fetch.timeout_seconds,
                user_agent=config.fetch.user_agent,
            )
        )
    raise ValueError("fetch_mode must be one of: fake, http")


def _provider_status_payload(config: AppConfig, database_url: str) -> dict[str, Any]:
    configured_provider = config.search_provider.provider.strip().lower()
    light_provider = config.llm.light_provider.strip().lower()
    heavy_provider = config.llm.heavy_provider.strip().lower()
    ollama_models = _ollama_models(config) if light_provider in {"ollama", "local"} else []
    return {
        "host": {
            "bind": config.infrastructure.host,
            "port": config.infrastructure.port,
            "database_url": _redacted_database_url(database_url),
        },
        "search": {
            "configured_provider": configured_provider,
            "configured_ready": _search_provider_ready(config, configured_provider),
            "brave_ready": _search_provider_ready(config, "brave"),
            "brave_configured": bool(
                config.search_provider.brave_api_key
                or config.search_provider.search_engine_token
            ),
            "mock_ready": True,
        },
        "llm": {
            "light": {
                "provider": light_provider,
                "model": config.llm.light_model,
                "configured": _llm_provider_ready(config, light_provider),
                "reachable": _ollama_reachable(config) if light_provider in {"ollama", "local"} else None,
                "models": ollama_models,
                "model_available": (
                    config.llm.light_model in ollama_models
                    if ollama_models
                    else None
                ),
            },
            "off": {"configured": True},
            "heavy": {
                "provider": heavy_provider,
                "model": config.llm.heavy_model,
                "configured": _llm_provider_ready(config, heavy_provider),
                "enabled_in_ui": False,
            },
        },
    }


def _run_result_payload(
    result,
    *,
    provider_mode: str,
    llm_mode: str,
    fetch_mode: str,
    phase_mode: str,
    search_provider: str,
) -> dict[str, Any]:
    return {
        "run": _pipeline_run_payload(result.run),
        "provider_mode": provider_mode,
        "llm_mode": llm_mode,
        "fetch_mode": fetch_mode,
        "phase_mode": phase_mode,
        "search_provider": search_provider,
        "review_target_count": result.review_target_count,
        "fetched_count": result.fetched_count,
        "evidence_count": result.evidence_count,
        "rated_count": result.rated_count,
        "drafted_count": result.drafted_count,
        "error_count": result.error_count,
        "import_statuses": [item.status.value for item in result.import_results],
    }


def _provider_mode(value: object) -> str:
    selected = str(value or "fake").strip().lower()
    if selected in {"mock"}:
        selected = "fake"
    if selected not in {"fake", "brave", "configured"}:
        raise ValueError("provider_mode must be one of: fake, brave, configured")
    return selected


def _fetch_mode(value: object, *, provider_mode: str) -> str:
    if value in {None, ""}:
        return "fake" if provider_mode == "fake" else "http"
    selected = str(value).strip().lower()
    if selected not in {"fake", "http"}:
        raise ValueError("fetch_mode must be one of: fake, http")
    return selected


def _phase_mode(value: object) -> str:
    selected = str(value or "full").strip().lower()
    if selected not in {"discovery", "fetch", "full", "rating"}:
        raise ValueError("phase_mode must be one of: discovery, fetch, full, rating")
    return selected


def _phases_for_mode(
    phase_mode: str,
    *,
    draft_enabled: bool,
) -> tuple[PipelinePhase, ...]:
    if phase_mode == "discovery":
        return (PipelinePhase.LEAD, PipelinePhase.IMPORT)
    if phase_mode == "fetch":
        return (
            PipelinePhase.LEAD,
            PipelinePhase.IMPORT,
            PipelinePhase.FETCH,
            PipelinePhase.EXTRACT,
        )
    if phase_mode == "rating":
        phases = (PipelinePhase.RATING,)
        return phases + ((PipelinePhase.DRAFT,) if draft_enabled else ())

    phases = (
        PipelinePhase.LEAD,
        PipelinePhase.IMPORT,
        PipelinePhase.FETCH,
        PipelinePhase.EXTRACT,
        PipelinePhase.RATING,
    )
    return phases + ((PipelinePhase.DRAFT,) if draft_enabled else ())


def _llm_mode(value: object) -> str:
    selected = str(value or "off").strip().lower()
    if selected not in {"off", "light"}:
        raise ValueError("llm_mode must be one of: off, light")
    return selected


def _bool_payload(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _optional_positive_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    parsed = int(value)
    if parsed <= 0:
        return None
    return parsed


def _required_positive_int(value: object, field_name: str) -> int:
    if value is None or value == "":
        raise ValueError(f"{field_name} is required")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be positive")
    return parsed


def _positive_int(value: object, *, default: int, maximum: int) -> int:
    if value is None or value == "":
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("numeric run values must be positive")
    return min(parsed, maximum)


def _tuple_payload(
    value: object,
    *,
    default: tuple[str, ...] = (),
) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    cleaned = tuple(str(item).strip() for item in items if str(item).strip())
    return cleaned or default


def _search_provider_ready(config: AppConfig, provider: str) -> bool:
    if provider in {"mock", "fake"}:
        return True
    if provider == "brave":
        return bool(config.search_provider.brave_api_key or config.search_provider.search_engine_token)
    return False


def _llm_provider_ready(config: AppConfig, provider: str) -> bool:
    if provider in {"fake", "mock", "ollama", "local"}:
        return True
    if provider == "openai":
        return bool(config.llm.openai_api_key)
    return False


def _ollama_reachable(config: AppConfig) -> bool:
    request = urllib.request.Request(f"{config.llm.local_base_url.rstrip('/')}/api/tags")
    try:
        with urllib.request.urlopen(request, timeout=1.2) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _redacted_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url
    if "@" in database_url:
        return database_url.split("@", 1)[1]
    return database_url


def _ollama_models(config: AppConfig) -> list[str]:
    request = urllib.request.Request(f"{config.llm.local_base_url.rstrip('/')}/api/tags")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []

    models = payload.get("models")
    if not isinstance(models, list):
        return []
    names = [
        str(item.get("name") or item.get("model") or "").strip()
        for item in models
        if isinstance(item, dict)
    ]
    return sorted(name for name in names if name)


def _domain_policy_payload(store: SQLiteStore) -> dict[str, Any]:
    blacklisted = [_domain_item(target) for target in store.list_targets_by_status(TargetStatus.BLACKLISTED)]
    rejected = store.list_rejected_domain_suggestions(min_count=1)
    return {
        "blacklisted": blacklisted,
        "rejected_suggestions": rejected,
        "counts": {
            "blacklisted": len(blacklisted),
            "rejected_suggestions": len(rejected),
        },
    }


def _domain_item(target: Target) -> dict[str, Any]:
    return {
        "id": target.id,
        "domain": target.domain,
        "base_url": target.base_url,
        "status": target.status.value,
        "source": target.source,
        "updated_at": _dt(target.updated_at),
    }


def _domain_from_payload(payload: dict[str, Any]) -> str:
    raw = str(payload.get("domain") or payload.get("url") or "").strip()
    if not raw:
        raise ValueError("domain is required")
    try:
        return domain_from_url(raw)
    except ValueError:
        return normalize_domain(raw)


def _blacklist_domain(store: SQLiteStore, domain: str) -> Target:
    existing = store.get_target_by_domain(domain)
    if existing is None:
        return store.create_target(
            Target(
                domain=domain,
                base_url=f"https://{domain}",
                source="manual",
                status=TargetStatus.BLACKLISTED,
                metadata={"policy": "manual_blacklist"},
            )
        )
    if existing.id is None:
        raise ValueError("target id is missing")
    store.set_target_status(
        existing.id,
        TargetStatus.BLACKLISTED,
        PipelinePhase.REVIEW,
        reason="manual domain blacklist",
        metadata={"trigger": "domain_policy"},
    )
    return store.get_target(existing.id)


def _unblock_domain(store: SQLiteStore, domain: str) -> Target:
    existing = store.get_target_by_domain(domain)
    if existing is None or existing.id is None:
        raise NotFoundError(f"domain not found: {domain}")
    store.set_target_status(
        existing.id,
        TargetStatus.REJECTED,
        PipelinePhase.REVIEW,
        reason="manual domain unblock",
        metadata={"trigger": "domain_policy"},
    )
    return store.get_target(existing.id)


def _run_preview_payload(store: SQLiteStore, payload: dict[str, Any]) -> dict[str, Any]:
    search_profile_id = _optional_positive_int(payload.get("search_profile_id"))
    use_case_id = _optional_positive_int(payload.get("use_case_id"))
    if search_profile_id is not None:
        search_profile = store.get_search_profile(search_profile_id)
        if use_case_id is not None and use_case_id != search_profile.use_case_id:
            search_profile = SearchProfile(
                id=search_profile.id,
                profile_id=search_profile.profile_id,
                use_case_id=use_case_id,
                name=search_profile.name,
                roles=search_profile.roles,
                regions=search_profile.regions,
                tech_keywords=search_profile.tech_keywords,
                industry_keywords=search_profile.industry_keywords,
                exclude_keywords=search_profile.exclude_keywords,
                attributes=search_profile.attributes,
                manual_query=search_profile.manual_query,
                draft_language=search_profile.draft_language,
                created_at=search_profile.created_at,
            )
        if _payload_has_search_values(payload):
            search_profile = SearchProfile(
                id=search_profile.id,
                profile_id=search_profile.profile_id,
                use_case_id=search_profile.use_case_id,
                name=search_profile.name,
                roles=(
                    _tuple_payload(payload.get("roles"))
                    if "roles" in payload
                    else search_profile.roles
                ),
                regions=(
                    _tuple_payload(payload.get("regions"))
                    if "regions" in payload
                    else search_profile.regions
                ),
                tech_keywords=(
                    _tuple_payload(payload.get("tech_keywords"))
                    if "tech_keywords" in payload
                    else search_profile.tech_keywords
                ),
                industry_keywords=(
                    _tuple_payload(payload.get("industry_keywords"))
                    if "industry_keywords" in payload
                    else search_profile.industry_keywords
                ),
                exclude_keywords=(
                    _tuple_payload(payload.get("exclude_keywords"))
                    if "exclude_keywords" in payload
                    else search_profile.exclude_keywords
                ),
                attributes=(
                    dict(payload.get("attributes") or {})
                    if "attributes" in payload
                    else search_profile.attributes
                ),
                manual_query=search_profile.manual_query,
                draft_language=search_profile.draft_language,
                created_at=search_profile.created_at,
            )
    else:
        search_profile = _search_profile_from_payload(
            payload,
            profile_id=1,
            default_name="Preview",
            store=store,
        )

    selected_use_case_id = use_case_id or search_profile.use_case_id
    use_case = store.get_use_case(selected_use_case_id) if selected_use_case_id else None
    request_budget = _positive_int(payload.get("request_budget"), default=10, maximum=100)
    queries = QueryBuilder().build(
        search_profile,
        template_set=None,
        limit=request_budget,
        use_case=use_case,
    )
    missing_required = _missing_required_fields(search_profile, use_case)
    source_policy = use_case.source_policy.to_dict() if use_case is not None else {}
    query_packs = []
    if use_case is not None:
        query_counts: dict[str, int] = {}
        for query in queries:
            if query.query_pack:
                query_counts[query.query_pack] = query_counts.get(query.query_pack, 0) + 1
        query_packs = [
            {
                "key": pack.key,
                "label": pack.label,
                "description": pack.description,
                "request_budget": pack.request_budget,
                "query_count": query_counts.get(pack.key, 0),
            }
            for pack in use_case.query_policy.query_packs
        ]
    return {
        "queries": [
            {
                "text": query.text,
                "template": query.query_template,
                "template_set": query.template_set,
                "query_pack": query.query_pack,
                "score": query.score,
            }
            for query in queries
        ],
        "query_packs": query_packs,
        "source_policy": source_policy,
        "missing_required": missing_required,
        "valid": not missing_required,
        "budget": {
            "request_budget": request_budget,
            "results_per_query": _positive_int(
                payload.get("results_per_query"),
                default=5,
                maximum=20,
            ),
        },
    }


def _missing_required_fields(
    search_profile: SearchProfile,
    use_case: UseCaseConfig | None,
) -> list[str]:
    if use_case is None:
        return []
    values = _search_profile_value_map(search_profile)
    missing: list[str] = []
    for field in use_case.attribute_schema.fields:
        if not field.required:
            continue
        value = values.get(field.key)
        if value is None or value == "" or value == []:
            missing.append(field.key)
    return missing


def _search_profile_value_map(search_profile: SearchProfile) -> dict[str, Any]:
    return {
        **dict(search_profile.attributes),
        "roles": list(search_profile.roles),
        "regions": list(search_profile.regions),
        "tech_keywords": list(search_profile.tech_keywords),
        "industry_keywords": list(search_profile.industry_keywords),
        "exclude_keywords": list(search_profile.exclude_keywords),
    }


def _parse_use_case_path(path: str) -> tuple[str, str | None]:
    raw = path.removeprefix("/api/use-cases/").strip("/")
    parts = raw.split("/")
    if not parts or not parts[0]:
        raise ValueError("missing use case slug")
    slug = parts[0]
    action = parts[1] if len(parts) > 1 else None
    return slug, action


def _use_case_payload(store: SQLiteStore, use_case: UseCaseConfig) -> dict[str, Any]:
    payload = use_case.to_dict()
    payload["db_id"] = store.get_use_case_id_by_slug(use_case.id)
    payload["slug"] = use_case.id
    payload["is_builtin"] = _is_builtin_use_case(use_case)
    payload["is_editable"] = not payload["is_builtin"]
    payload["origin"] = use_case.created_from_template or (
        "built_in" if payload["is_builtin"] else "local"
    )
    return payload


def _use_case_export_payload(use_case: UseCaseConfig) -> dict[str, Any]:
    return {
        "format": "target-radar-use-case-v1",
        "use_case": use_case.to_dict(),
    }


def _import_config_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_config = payload.get("config")
    if raw_config is None:
        raw_config = payload.get("use_case")
    if raw_config is None and payload.get("format") == "target-radar-use-case-v1":
        raw_config = payload.get("use_case")
    if raw_config is None:
        raw_config = payload
    if not isinstance(raw_config, dict):
        raise ValueError("import payload must contain a use_case object")
    config = dict(raw_config)
    config.pop("db_id", None)
    config.pop("slug", None)
    return config


def _import_use_case(
    store: SQLiteStore,
    config: dict[str, Any],
    *,
    conflict: str,
) -> tuple[UseCaseConfig, str]:
    if conflict not in {"reject", "rename", "overwrite"}:
        raise ValueError("conflict must be one of: reject, rename, overwrite")

    selected = validate_use_case_config(config)
    exists = _use_case_slug_exists(store, selected.id)
    if not exists:
        store.save_use_case(selected)
        return store.get_use_case_by_slug(selected.id), "created"

    if conflict == "reject":
        raise UseCaseImportConflict(f"use case already exists: {selected.id}")

    if conflict == "overwrite":
        existing_use_case = store.get_use_case_by_slug(selected.id)
        if _is_builtin_use_case(existing_use_case):
            raise ValueError("built-in use case templates cannot be overwritten")
        store.save_use_case(selected)
        return store.get_use_case_by_slug(selected.id), "overwritten"

    renamed_payload = selected.to_dict()
    renamed_payload["id"] = _unique_import_slug(store, selected.id)
    renamed_payload["name"] = f"{selected.name} Import"
    renamed_payload["created_from_template"] = selected.created_from_template or selected.id
    renamed = validate_use_case_config(renamed_payload)
    store.save_use_case(renamed)
    return store.get_use_case_by_slug(renamed.id), "renamed"


def _clone_use_case(
    store: SQLiteStore,
    source: UseCaseConfig,
    *,
    name: object = None,
    slug: object = None,
) -> UseCaseConfig:
    selected_slug = str(slug or "").strip()
    if selected_slug:
        selected_slug = _slugify(selected_slug)
        if _use_case_slug_exists(store, selected_slug):
            raise ValueError(f"use case already exists: {selected_slug}")
    else:
        selected_slug = _unique_clone_slug(store, source.id)

    payload = source.to_dict()
    payload["id"] = selected_slug
    payload["name"] = str(name or f"{source.name} Copy").strip()
    payload["status"] = "active"
    payload["created_from_template"] = source.created_from_template or source.id
    cloned = validate_use_case_config(payload)
    store.save_use_case(cloned)
    return store.get_use_case_by_slug(cloned.id)


def _unique_clone_slug(store: SQLiteStore, source_slug: str) -> str:
    base = _slugify(f"{source_slug}_copy")
    return _unique_slug(store, base)


def _unique_import_slug(store: SQLiteStore, source_slug: str) -> str:
    base = _slugify(f"{source_slug}_import")
    return _unique_slug(store, base)


def _unique_slug(store: SQLiteStore, base: str) -> str:
    candidate = base
    suffix = 2
    while _use_case_slug_exists(store, candidate):
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _use_case_slug_exists(store: SQLiteStore, slug: str) -> bool:
    try:
        store.get_use_case_id_by_slug(slug)
    except NotFoundError:
        return False
    return True


def _is_builtin_use_case(use_case: UseCaseConfig) -> bool:
    return (
        use_case.status == UseCaseStatus.TEMPLATE
        and use_case.created_from_template is None
    )


def _slugify(value: str) -> str:
    cleaned = "".join(
        char.lower() if ("a" <= char.lower() <= "z" or char.isdigit()) else "_"
        for char in value.strip()
    )
    parts = [part for part in cleaned.split("_") if part]
    slug = "_".join(parts)
    if not slug:
        raise ValueError("use case slug must not be empty")
    if not slug[0].isalpha():
        slug = f"use_case_{slug}"
    return slug


def _target_context(
    store: SQLiteStore,
    target_id: int,
) -> tuple[Profile, SearchProfile]:
    run = store.get_latest_pipeline_run_for_target(target_id)
    if run is None:
        raise ValueError("target has no pipeline context for reprocessing")
    search_profile = store.get_search_profile(run.search_profile_id)
    profile = store.get_profile(search_profile.profile_id)
    return profile, search_profile


def _fake_reprocess_orchestrator(
    *,
    store: SQLiteStore,
    profile: Profile,
    search_profile: SearchProfile,
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        store,
        FakeLeadEngine(),
        fetcher=GeneratedFakeFetcher(terms=_search_terms(search_profile)),
        extractor=HtmlExtractor(),
        rating_engine=RatingEngine(ai_provider=FakeAIRatingProvider()),
        draft_engine=DraftEngine(),
        profile=profile,
        max_pages_per_target=2,
    )


def _reprocess_result_payload(result) -> dict[str, Any]:
    return {
        "target": _target_payload(result.target),
        "review_target_count": result.review_target_count,
        "fetched_count": result.fetched_count,
        "evidence_count": result.evidence_count,
        "rated_count": result.rated_count,
        "drafted_count": result.drafted_count,
        "error_count": result.error_count,
    }


def _parse_target_path(path: str) -> tuple[int, str | None]:
    raw = path.removeprefix("/api/targets/").strip("/")
    parts = raw.split("/")
    if not parts or not parts[0]:
        raise ValueError("missing target id")
    target_id = int(parts[0])
    action = parts[1] if len(parts) > 1 else None
    return target_id, action


def _attach_context_source_evidence(
    store: SQLiteStore,
    *,
    target_id: int,
    context_source_id: int,
):
    store.get_target(target_id)
    context_source = store.get_context_source(context_source_id)
    if not _is_attachable_context_source(context_source):
        raise ValueError("context_source_id must reference a context source")

    existing = _existing_context_source_evidence(
        store,
        target_id=target_id,
        context_source_id=context_source_id,
    )
    if existing is not None:
        store.assign_context_source_to_target(context_source_id, target_id)
        return existing

    evidence = EvidenceEngine().from_context_source(
        target_id=target_id,
        context_source=context_source,
    )
    if evidence is None:
        raise ValueError("context source has no usable evidence text")
    saved = store.add_evidence(evidence)
    store.assign_context_source_to_target(context_source_id, target_id)
    return saved


def _existing_context_source_evidence(
    store: SQLiteStore,
    *,
    target_id: int,
    context_source_id: int,
):
    for evidence in store.list_evidence(target_id):
        if evidence.metadata.get("context_source_id") == context_source_id:
            return evidence
    return None


def _is_attachable_context_source(item: dict[str, Any]) -> bool:
    if item.get("status") == "review_source":
        return True
    if item.get("import_status") == "review_source":
        return True
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        return False
    source_quality = metadata.get("source_quality")
    if not isinstance(source_quality, dict):
        return False
    return source_quality.get("recommended_import_action") == "review_source"


def _pipeline_run_payload(run) -> dict[str, Any]:
    return {
        "id": run.id,
        "search_profile_id": run.search_profile_id,
        "use_case_id": run.use_case_id,
        "use_case_version": run.use_case_version,
        "use_case_slug": run.use_case_snapshot.get("id"),
        "use_case_name": run.use_case_snapshot.get("name"),
        "mode": run.mode,
        "status": run.status.value,
        "phases": [phase.value for phase in run.phases],
        "request_budget": run.request_budget,
        "results_per_query": run.results_per_query,
        "stats": run.stats,
        "error_message": run.error_message,
        "started_at": _dt(run.started_at),
        "finished_at": _dt(run.finished_at),
        "created_at": _dt(run.created_at),
    }


def _context_source_payload(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    source_quality = metadata.get("source_quality")
    if not isinstance(source_quality, dict):
        source_quality = {}
    return {
        "id": item["id"],
        "source_query_id": item["source_query_id"],
        "target_id": item["target_id"],
        "pipeline_run_id": item["pipeline_run_id"],
        "search_profile_id": item["search_profile_id"],
        "use_case_id": item["use_case_id"],
        "use_case_slug": item["use_case_slug"],
        "use_case_name": item["use_case_name"],
        "provider": item["provider"],
        "query_text": item["query_text"],
        "query_template": item["query_template"],
        "template_set": item["template_set"],
        "query_score": item["query_score"],
        "url": item["url"],
        "domain": item["domain"],
        "title": item["title"],
        "snippet": item["snippet"],
        "status": item["status"],
        "import_status": item["import_status"],
        "source_type": source_quality.get("source_type"),
        "source_quality_score": source_quality.get("source_quality_score"),
        "recommended_import_action": source_quality.get("recommended_import_action"),
        "source_signals": source_quality.get("source_signals") or [],
        "source_risks": source_quality.get("source_risks") or [],
        "metadata": metadata,
        "created_at": item["created_at"],
    }


def _target_payload(target) -> dict[str, Any]:
    return {
        "id": target.id,
        "domain": target.domain,
        "base_url": target.base_url,
        "source": target.source,
        "status": target.status.value,
        "metadata": target.metadata,
        "created_at": _dt(target.created_at),
        "updated_at": _dt(target.updated_at),
    }


def _target_page_payload(page) -> dict[str, Any]:
    return {
        "id": page.id,
        "target_id": page.target_id,
        "url": page.url,
        "page_type": page.page_type,
        "http_status": page.http_status,
        "title": page.title,
        "text": page.text,
        "error_message": page.error_message,
        "metadata": page.metadata,
        "fetched_at": _dt(page.fetched_at),
        "created_at": _dt(page.created_at),
    }


def _evidence_payload(evidence) -> dict[str, Any]:
    return {
        "id": evidence.id,
        "target_id": evidence.target_id,
        "page_id": evidence.page_id,
        "source_url": evidence.source_url,
        "text": evidence.text,
        "context_type": evidence.context_type,
        "priority": evidence.priority,
        "metadata": evidence.metadata,
        "created_at": _dt(evidence.created_at),
    }


def _rating_payload(rating) -> dict[str, Any]:
    payload = asdict(rating)
    payload["recommended_action"] = rating.recommended_action.value
    payload["created_at"] = _dt(rating.created_at)
    return payload


def _draft_payload(draft) -> dict[str, Any]:
    payload = asdict(draft)
    payload["status"] = draft.status.value
    payload["created_at"] = _dt(draft.created_at)
    payload["updated_at"] = _dt(draft.updated_at)
    return payload


def _status_log_payload(log) -> dict[str, Any]:
    return {
        "id": log.id,
        "target_id": log.target_id,
        "pipeline_run_id": log.pipeline_run_id,
        "from_status": log.from_status.value if log.from_status else None,
        "to_status": log.to_status.value,
        "phase": log.phase.value,
        "reason": log.reason,
        "error_message": log.error_message,
        "metadata": log.metadata,
        "created_at": _dt(log.created_at),
    }


def _search_profile_payload(search_profile: SearchProfile) -> dict[str, Any]:
    return {
        "id": search_profile.id,
        "profile_id": search_profile.profile_id,
        "use_case_id": search_profile.use_case_id,
        "name": search_profile.name,
        "roles": list(search_profile.roles),
        "regions": list(search_profile.regions),
        "tech_keywords": list(search_profile.tech_keywords),
        "industry_keywords": list(search_profile.industry_keywords),
        "exclude_keywords": list(search_profile.exclude_keywords),
        "attributes": search_profile.attributes,
        "manual_query": search_profile.manual_query,
        "draft_language": search_profile.draft_language,
        "created_at": _dt(search_profile.created_at),
    }


def _search_terms(search_profile: SearchProfile) -> tuple[str, ...]:
    attribute_terms: list[str] = []
    for value in search_profile.attributes.values():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            attribute_terms.extend(str(item) for item in value if item is not None)
        else:
            attribute_terms.append(str(value))
    return (
        search_profile.roles
        + search_profile.regions
        + search_profile.tech_keywords
        + search_profile.industry_keywords
        + tuple(item.strip() for item in attribute_terms if item.strip())
    )


def _dt(value) -> str | None:
    return value.isoformat() if value is not None else None
