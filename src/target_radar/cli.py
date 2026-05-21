"""Local command line interface for Target Radar."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from target_radar.config import load_app_config
from target_radar.domain import Profile, SearchProfile
from target_radar.engines.lead import FakeLeadEngine
from target_radar.pipeline import PipelineOrchestrator, PipelineRunRequest
from target_radar.storage import SQLiteStore
from target_radar.web.server import serve


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    database_url = args.database_url or load_app_config().infrastructure.database_url

    if args.command == "init-db":
        store = SQLiteStore.open(database_url)
        store.close()
        _print_json({"database_url": database_url, "status": "initialized"})
        return 0

    if args.command == "run-fake":
        return _run_fake(args, database_url)

    if args.command == "review-queue":
        return _review_queue(args, database_url)

    if args.command == "serve":
        serve(database_url=database_url, host=args.host, port=args.port)
        return 0

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="target-radar")
    parser.add_argument("--database-url", help="SQLite URL or path")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init-db", help="Initialize the local database")

    run_fake = subparsers.add_parser("run-fake", help="Run deterministic fake pipeline")
    run_fake.add_argument("--profile-name", default="Local Profile")
    run_fake.add_argument("--search-name", default="Local Search")
    run_fake.add_argument("--role", action="append", default=[])
    run_fake.add_argument("--region", action="append", default=[])
    run_fake.add_argument("--tech", action="append", default=[])
    run_fake.add_argument("--request-budget", type=int, default=10)
    run_fake.add_argument("--results-per-query", type=int, default=5)

    review_queue = subparsers.add_parser("review-queue", help="Print review targets")
    review_queue.add_argument("--limit", type=int, default=50)
    review_queue.add_argument("--offset", type=int, default=0)

    serve_parser = subparsers.add_parser("serve", help="Run local web UI")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    return parser


def _run_fake(args, database_url: str) -> int:
    store = SQLiteStore.open(database_url)
    try:
        profile = store.create_profile(Profile(name=args.profile_name))
        search_profile = store.create_search_profile(
            SearchProfile(
                profile_id=profile.id,
                name=args.search_name,
                roles=tuple(args.role or ["Werkstudent IT"]),
                regions=tuple(args.region or ["Essen"]),
                tech_keywords=tuple(args.tech or ["Python"]),
            )
        )
        result = PipelineOrchestrator(store, FakeLeadEngine()).run(
            PipelineRunRequest(
                search_profile=search_profile,
                request_budget=args.request_budget,
                results_per_query=args.results_per_query,
            )
        )
        _print_json(
            {
                "run_id": result.run.id,
                "status": result.run.status.value,
                "review_target_count": result.review_target_count,
                "import_statuses": [
                    item.status.value for item in result.import_results
                ],
            }
        )
        return 0
    finally:
        store.close()


def _review_queue(args, database_url: str) -> int:
    store = SQLiteStore.open(database_url)
    try:
        targets = store.list_review_targets(limit=args.limit, offset=args.offset)
        _print_json(
            {
                "targets": [
                    {
                        "id": target.id,
                        "domain": target.domain,
                        "status": target.status.value,
                        "source": target.source,
                    }
                    for target in targets
                ]
            }
        )
        return 0
    finally:
        store.close()


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
