"""Local command line interface for Target Radar."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from target_radar.config import load_app_config
from target_radar.domain import PipelinePhase, Profile, SearchProfile
from target_radar.engines.draft import DraftEngine
from target_radar.engines.lead import (
    FakeLeadEngine,
    LeadEngineConfig,
    create_lead_engine,
)
from target_radar.engines.rating import FakeAIRatingProvider, RatingEngine, create_rating_engine
from target_radar.evaluation import (
    DEFAULT_EVALUATION_FIXTURE,
    DEFAULT_RUN_REPORT_OUTPUT,
    DEFAULT_REVIEW_EVALUATION_OUTPUT,
    export_pipeline_run_report,
    export_review_feedback_fixture,
    run_evaluation,
)
from target_radar.ops import collect_diagnostics, configure_logging, run_privacy_check
from target_radar.pipeline import (
    FetchConfig as PipelineFetchConfig,
    GeneratedFakeFetcher,
    HtmlExtractor,
    HttpFetcher,
    PipelineOrchestrator,
    PipelineRunRequest,
)
from target_radar.storage import SQLiteStore
from target_radar.web.server import serve


FULL_PIPELINE_PHASES = (
    PipelinePhase.LEAD,
    PipelinePhase.IMPORT,
    PipelinePhase.FETCH,
    PipelinePhase.EXTRACT,
    PipelinePhase.RATING,
    PipelinePhase.DRAFT,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_app_config()
    database_url = args.database_url or config.infrastructure.database_url
    log_level = args.log_level or config.infrastructure.log_level
    log_file = args.log_file or config.infrastructure.log_file
    if args.command == "serve" or args.log_file:
        configure_logging(level=log_level, log_file=log_file)

    if args.command == "init-db":
        store = SQLiteStore.open(database_url)
        store.close()
        _print_json({"database_url": database_url, "status": "initialized"})
        return 0

    if args.command == "run-fake":
        return _run_fake(args, database_url)

    if args.command == "run-configured":
        return _run_configured(args, database_url, config)

    if args.command == "review-queue":
        return _review_queue(args, database_url)

    if args.command == "serve":
        serve(
            database_url=database_url,
            host=args.host or config.infrastructure.host,
            port=args.port or config.infrastructure.port,
        )
        return 0

    if args.command == "diagnose":
        _print_json(collect_diagnostics(database_url))
        return 0

    if args.command == "evaluate":
        _print_json(run_evaluation(args.fixture))
        return 0

    if args.command == "export-review-eval":
        _print_json(
            export_review_feedback_fixture(
                database_url,
                output_path=args.output,
                limit=args.limit,
            )
        )
        return 0

    if args.command == "export-run-report":
        _print_json(
            export_pipeline_run_report(
                database_url,
                run_id=args.run_id,
                output_path=args.output,
                review_limit=args.review_limit,
            )
        )
        return 0

    if args.command == "privacy-check":
        result = run_privacy_check(args.root)
        _print_json(result)
        return 0 if result["ok"] else 1

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="target-radar")
    parser.add_argument("--database-url", help="SQLite URL or path")
    parser.add_argument("--log-level")
    parser.add_argument("--log-file", help="Optional JSON-lines log file")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init-db", help="Initialize the local database")

    run_fake = subparsers.add_parser("run-fake", help="Run deterministic fake pipeline")
    _add_run_arguments(run_fake)

    run_configured = subparsers.add_parser(
        "run-configured",
        help="Run pipeline with configured search provider",
    )
    _add_run_arguments(run_configured)

    review_queue = subparsers.add_parser("review-queue", help="Print review targets")
    review_queue.add_argument("--limit", type=int, default=50)
    review_queue.add_argument("--offset", type=int, default=0)

    serve_parser = subparsers.add_parser("serve", help="Run local web UI")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)

    subparsers.add_parser("diagnose", help="Print local diagnostic snapshot")

    evaluate = subparsers.add_parser("evaluate", help="Run deterministic engine evals")
    evaluate.add_argument("--fixture", default=DEFAULT_EVALUATION_FIXTURE)

    export_review_eval = subparsers.add_parser(
        "export-review-eval",
        help="Export local review decisions as an eval fixture",
    )
    export_review_eval.add_argument("--output", default=DEFAULT_REVIEW_EVALUATION_OUTPUT)
    export_review_eval.add_argument("--limit", type=int, default=50)

    export_run_report = subparsers.add_parser(
        "export-run-report",
        help="Export a pipeline run report with review backlog and feedback triage",
    )
    export_run_report.add_argument("--run-id", type=int)
    export_run_report.add_argument("--output", default=DEFAULT_RUN_REPORT_OUTPUT)
    export_run_report.add_argument("--review-limit", type=int, default=100)

    privacy = subparsers.add_parser("privacy-check", help="Check local privacy guardrails")
    privacy.add_argument("--root", default=".")
    return parser


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile-name", default="Local Profile")
    parser.add_argument("--search-name", default="Local Search")
    parser.add_argument("--role", action="append", default=[])
    parser.add_argument("--region", action="append", default=[])
    parser.add_argument("--tech", action="append", default=[])
    parser.add_argument("--request-budget", type=int, default=10)
    parser.add_argument("--results-per-query", type=int, default=5)


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
        result = PipelineOrchestrator(
            store,
            FakeLeadEngine(),
            fetcher=GeneratedFakeFetcher(terms=_search_terms(search_profile)),
            extractor=HtmlExtractor(),
            rating_engine=RatingEngine(ai_provider=FakeAIRatingProvider()),
            draft_engine=DraftEngine(),
            profile=profile,
            max_pages_per_target=2,
        ).run(
            PipelineRunRequest(
                search_profile=search_profile,
                phases=FULL_PIPELINE_PHASES,
                request_budget=args.request_budget,
                results_per_query=args.results_per_query,
            )
        )
        _print_json(
            {
                "run_id": result.run.id,
                "status": result.run.status.value,
                "review_target_count": result.review_target_count,
                "fetched_count": result.fetched_count,
                "evidence_count": result.evidence_count,
                "rated_count": result.rated_count,
                "drafted_count": result.drafted_count,
                "error_count": result.error_count,
                "import_statuses": [
                    item.status.value for item in result.import_results
                ],
            }
        )
        return 0
    finally:
        store.close()


def _run_configured(args, database_url: str, config) -> int:
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
        lead_engine = create_lead_engine(config, store=store)
        lead_engine.config = LeadEngineConfig(
            request_budget=args.request_budget,
            results_per_query=args.results_per_query,
            template_set=lead_engine.config.template_set,
            source_block_threshold=lead_engine.config.source_block_threshold,
        )
        result = PipelineOrchestrator(
            store,
            lead_engine,
            fetcher=HttpFetcher(
                PipelineFetchConfig(
                    timeout_seconds=config.fetch.timeout_seconds,
                    user_agent=config.fetch.user_agent,
                )
            ),
            extractor=HtmlExtractor(),
            rating_engine=create_rating_engine(config),
            draft_engine=DraftEngine(),
            profile=profile,
            max_pages_per_target=config.fetch.max_pages_per_target,
        ).run(
            PipelineRunRequest(
                search_profile=search_profile,
                phases=FULL_PIPELINE_PHASES,
                request_budget=args.request_budget,
                results_per_query=args.results_per_query,
            )
        )
        _print_json(
            {
                "run_id": result.run.id,
                "status": result.run.status.value,
                "search_provider": lead_engine.provider.name,
                "review_target_count": result.review_target_count,
                "fetched_count": result.fetched_count,
                "evidence_count": result.evidence_count,
                "rated_count": result.rated_count,
                "drafted_count": result.drafted_count,
                "error_count": result.error_count,
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


def _search_terms(search_profile: SearchProfile) -> tuple[str, ...]:
    return (
        search_profile.roles
        + search_profile.regions
        + search_profile.tech_keywords
        + search_profile.industry_keywords
    )


if __name__ == "__main__":
    raise SystemExit(main())
