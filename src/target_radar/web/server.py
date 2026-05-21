"""Local-only HTTP server for the Target Radar UI."""

from __future__ import annotations

import json
import logging
import mimetypes
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from target_radar.domain import (
    PipelinePhase,
    Profile,
    SearchProfile,
    TargetStatus,
)
from target_radar.engines.lead import FakeLeadEngine
from target_radar.pipeline import PipelineOrchestrator, PipelineRunRequest
from target_radar.storage import NotFoundError, SQLiteStore


STATIC_DIR = Path(__file__).with_name("static")
LOGGER = logging.getLogger(__name__)


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
) -> ThreadingHTTPServer:
    handler = _make_handler(database_url)
    return ThreadingHTTPServer((host, port), handler)


def _make_handler(database_url: str):
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
                if parsed.path.startswith("/api/drafts/"):
                    self._handle_draft_patch(parsed.path)
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

        def _handle_review_queue(self, query: str) -> None:
            params = parse_qs(query)
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])
            store = self._store()
            try:
                self._send_json(
                    {
                        "items": store.list_review_queue_items(
                            limit=limit,
                            offset=offset,
                        )
                    }
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
            store = self._store()
            try:
                profile = store.create_profile(
                    Profile(name=str(payload.get("profile_name") or "Local Profile"))
                )
                search_profile = store.create_search_profile(
                    SearchProfile(
                        profile_id=profile.id,
                        name=str(payload.get("search_name") or "Local Search"),
                        roles=tuple(payload.get("roles") or ["Werkstudent IT"]),
                        regions=tuple(payload.get("regions") or ["Essen"]),
                        tech_keywords=tuple(payload.get("tech_keywords") or ["Python"]),
                    )
                )
                result = PipelineOrchestrator(store, FakeLeadEngine()).run(
                    PipelineRunRequest(
                        search_profile=search_profile,
                        request_budget=int(payload.get("request_budget") or 10),
                        results_per_query=int(payload.get("results_per_query") or 5),
                    )
                )
                self._send_json(
                    {
                        "run": _pipeline_run_payload(result.run),
                        "review_target_count": result.review_target_count,
                        "import_statuses": [
                            item.status.value for item in result.import_results
                        ],
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


def _parse_id_path(path: str, prefix: str) -> int:
    raw = path.removeprefix(prefix).strip("/")
    if "/" in raw or not raw:
        raise ValueError("invalid id path")
    return int(raw)


def _parse_target_path(path: str) -> tuple[int, str | None]:
    raw = path.removeprefix("/api/targets/").strip("/")
    parts = raw.split("/")
    if not parts or not parts[0]:
        raise ValueError("missing target id")
    target_id = int(parts[0])
    action = parts[1] if len(parts) > 1 else None
    return target_id, action


def _pipeline_run_payload(run) -> dict[str, Any]:
    return {
        "id": run.id,
        "search_profile_id": run.search_profile_id,
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


def _dt(value) -> str | None:
    return value.isoformat() if value is not None else None
