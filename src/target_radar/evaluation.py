"""Deterministic engine evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from target_radar.config import RatingConfig
from target_radar.domain import (
    Evidence,
    Profile,
    RatingResult,
    RecommendedAction,
    SearchProfile,
    Target,
    TargetStatus,
    domain_from_url,
)
from target_radar.engines.draft import DraftEngine, DraftSkippedError
from target_radar.engines.lead import SearchResult
from target_radar.engines.lead.source_quality import SourceQualityClassifier
from target_radar.engines.rating import AIRatingResponse, FakeAIRatingProvider, RatingEngine
from target_radar.storage import SQLiteStore
from target_radar.use_cases import get_default_use_case


DEFAULT_EVALUATION_FIXTURE = "docs/evaluation/engine-eval-baseline.json"
DEFAULT_REVIEW_EVALUATION_OUTPUT = "exports/local-review-eval.json"
DEFAULT_RUN_REPORT_OUTPUT = "exports/local-run-report.json"
_REVIEW_EXPECTED_ACTION = {
    "approved": "draft",
    "rejected": "skip",
    "blacklisted": "skip",
}


def run_evaluation(fixture_path: str | Path = DEFAULT_EVALUATION_FIXTURE) -> dict[str, Any]:
    payload = _load_fixture(fixture_path)
    sections = {
        "source_quality": _run_source_quality_cases(payload.get("source_quality", [])),
        "rating": _run_rating_cases(payload.get("rating", [])),
        "draft": _run_draft_cases(payload.get("draft", [])),
        "review_feedback": _run_review_feedback_cases(
            payload.get("review_feedback", [])
        ),
    }
    total = sum(section["total"] for section in sections.values())
    passed = sum(section["passed"] for section in sections.values())
    return {
        "suite": payload.get("name", "engine_eval"),
        "source": payload.get("source"),
        "status": "passed" if passed == total else "failed",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": _ratio(passed, total),
        "sections": sections,
    }


def export_review_feedback_fixture(
    database_url: str,
    *,
    output_path: str | Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    store = SQLiteStore.open(database_url)
    try:
        cases = _review_feedback_cases(store, limit=limit)
    finally:
        store.close()

    payload = {
        "name": "local_review_feedback",
        "source": "local SQLite review decisions",
        "review_feedback": cases,
        "summary": {
            "total": len(cases),
            "approved": sum(1 for case in cases if case["review_status"] == "approved"),
            "rejected": sum(1 for case in cases if case["review_status"] == "rejected"),
            "blacklisted": sum(
                1 for case in cases if case["review_status"] == "blacklisted"
            ),
        },
    }
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(path)
    return payload


def export_pipeline_run_report(
    database_url: str,
    *,
    run_id: int | None = None,
    output_path: str | Path | None = None,
    review_limit: int = 100,
) -> dict[str, Any]:
    store = SQLiteStore.open(database_url)
    try:
        run = (
            store.get_pipeline_run(run_id)
            if run_id is not None
            else _latest_pipeline_run(store)
        )
        if run is None or run.id is None:
            raise ValueError("no pipeline run found")
        review_cases = _review_feedback_cases(store, limit=review_limit)
        review_section = _run_review_feedback_cases(review_cases)
        payload = {
            "name": "local_pipeline_run_report",
            "source": "local SQLite pipeline run",
            "run": _run_report_run(run),
            "queries": _run_report_queries(store, run.id),
            "targets": _run_report_targets(store, run.id),
            "review_backlog": _run_review_backlog(store, run.id),
            "review_feedback": {
                "summary": {
                    "total": len(review_cases),
                    "approved": sum(
                        1 for case in review_cases if case["review_status"] == "approved"
                    ),
                    "rejected": sum(
                        1 for case in review_cases if case["review_status"] == "rejected"
                    ),
                    "blacklisted": sum(
                        1
                        for case in review_cases
                        if case["review_status"] == "blacklisted"
                    ),
                },
                "evaluation": review_section,
            },
        }
    finally:
        store.close()

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(path)
    return payload


def _latest_pipeline_run(store: SQLiteStore):
    runs = store.list_pipeline_runs(limit=1)
    return runs[0] if runs else None


def _run_report_run(run) -> dict[str, Any]:
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
        "stats": dict(run.stats),
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "created_at": run.created_at.isoformat(),
    }


def _run_report_queries(store: SQLiteStore, run_id: int) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        """
        SELECT
            source_queries.id,
            source_queries.provider,
            source_queries.query_text,
            source_queries.query_template,
            source_queries.template_set,
            source_queries.query_score,
            source_queries.status,
            COUNT(serp_results.id) AS result_count,
            SUM(CASE WHEN serp_results.status = 'candidate' THEN 1 ELSE 0 END)
                AS candidate_count,
            SUM(CASE WHEN serp_results.status = 'duplicate_domain' THEN 1 ELSE 0 END)
                AS duplicate_domain_count,
            SUM(CASE WHEN serp_results.status = 'review_source' THEN 1 ELSE 0 END)
                AS review_source_status_count,
            SUM(CASE WHEN serp_results.status = 'blocked_source' THEN 1 ELSE 0 END)
                AS blocked_source_status_count,
            SUM(CASE WHEN serp_results.status = 'blacklisted' THEN 1 ELSE 0 END)
                AS blacklisted_status_count,
            SUM(CASE WHEN serp_results.status = 'invalid' THEN 1 ELSE 0 END)
                AS invalid_status_count,
            SUM(CASE WHEN serp_results.import_status = 'imported' THEN 1 ELSE 0 END)
                AS imported_count,
            SUM(CASE WHEN serp_results.import_status = 'existing' THEN 1 ELSE 0 END)
                AS existing_count,
            SUM(CASE WHEN serp_results.import_status = 'duplicate_input' THEN 1 ELSE 0 END)
                AS duplicate_count,
            SUM(CASE WHEN serp_results.import_status = 'review_source' THEN 1 ELSE 0 END)
                AS review_source_count,
            SUM(CASE WHEN serp_results.import_status = 'blocked_source' THEN 1 ELSE 0 END)
                AS blocked_source_count,
            SUM(CASE WHEN serp_results.import_status = 'blacklisted' THEN 1 ELSE 0 END)
                AS blacklisted_count
        FROM source_queries
        LEFT JOIN serp_results
            ON serp_results.source_query_id = source_queries.id
        WHERE source_queries.pipeline_run_id = ?
        GROUP BY source_queries.id
        ORDER BY source_queries.id ASC
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "provider": row["provider"],
            "query_text": row["query_text"],
            "query_template": row["query_template"],
            "template_set": row["template_set"],
            "query_score": row["query_score"],
            "status": row["status"],
            "result_count": row["result_count"],
            "result_status_counts": {
                "candidate": row["candidate_count"] or 0,
                "duplicate_domain": row["duplicate_domain_count"] or 0,
                "review_source": row["review_source_status_count"] or 0,
                "blocked_source": row["blocked_source_status_count"] or 0,
                "blacklisted": row["blacklisted_status_count"] or 0,
                "invalid": row["invalid_status_count"] or 0,
            },
            "import_status_counts": {
                "imported": row["imported_count"] or 0,
                "existing": row["existing_count"] or 0,
                "duplicate_input": row["duplicate_count"] or 0,
                "review_source": row["review_source_count"] or 0,
                "blocked_source": row["blocked_source_count"] or 0,
                "blacklisted": row["blacklisted_count"] or 0,
            },
        }
        for row in rows
    ]


def _run_report_targets(store: SQLiteStore, run_id: int) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        """
        WITH run_targets AS (
            SELECT DISTINCT target_id
            FROM target_scores
            WHERE pipeline_run_id = ?
            UNION
            SELECT DISTINCT target_id
            FROM target_status_log
            WHERE pipeline_run_id = ?
            UNION
            SELECT DISTINCT serp_results.target_id
            FROM serp_results
            INNER JOIN source_queries
                ON source_queries.id = serp_results.source_query_id
            WHERE source_queries.pipeline_run_id = ?
              AND serp_results.target_id IS NOT NULL
        )
        SELECT
            targets.id,
            targets.domain,
            targets.base_url,
            targets.source,
            targets.status,
            scores.recommended_action,
            scores.rating_status,
            scores.rule_score,
            scores.ai_score,
            scores.confidence,
            scores.risks_json,
            latest_review.to_status AS review_status,
            latest_review.reason AS review_reason,
            (
                SELECT COUNT(*)
                FROM evidence
                WHERE evidence.target_id = targets.id
            ) AS evidence_count,
            (
                SELECT COUNT(*)
                FROM action_drafts
                WHERE action_drafts.target_id = targets.id
            ) AS draft_count
        FROM run_targets
        INNER JOIN targets
            ON targets.id = run_targets.target_id
        LEFT JOIN target_scores AS scores
            ON scores.id = (
                SELECT id
                FROM target_scores
                WHERE target_scores.target_id = targets.id
                  AND target_scores.pipeline_run_id = ?
                ORDER BY id DESC
                LIMIT 1
            )
        LEFT JOIN target_status_log AS latest_review
            ON latest_review.id = (
                SELECT id
                FROM target_status_log
                WHERE target_status_log.target_id = targets.id
                  AND target_status_log.phase = 'review'
                  AND target_status_log.to_status IN (
                      'approved',
                      'rejected',
                      'blacklisted'
                  )
                ORDER BY id DESC
                LIMIT 1
            )
        ORDER BY
            CASE scores.recommended_action
                WHEN 'draft' THEN 0
                WHEN 'review' THEN 1
                WHEN 'skip' THEN 2
                ELSE 3
            END,
            COALESCE(scores.ai_score, scores.rule_score, 0) DESC,
            targets.domain ASC
        """,
        (run_id, run_id, run_id, run_id),
    ).fetchall()
    return [
        {
            "target_id": row["id"],
            "domain": row["domain"],
            "base_url": row["base_url"],
            "source": row["source"],
            "status": row["status"],
            "recommended_action": row["recommended_action"],
            "rating_status": row["rating_status"],
            "rule_score": row["rule_score"],
            "ai_score": row["ai_score"],
            "confidence": row["confidence"],
            "risk_types": _risk_types(row["risks_json"]),
            "evidence_count": row["evidence_count"],
            "draft_count": row["draft_count"],
            "review_status": row["review_status"],
            "review_reason": row["review_reason"],
        }
        for row in rows
    ]


def _run_review_backlog(store: SQLiteStore, run_id: int) -> dict[str, Any]:
    targets = _run_report_targets(store, run_id)
    reviewable_statuses = {
        "needs_review",
        "rating_partial",
        "draft_pending",
        "draft_failed",
    }
    backlog = [
        item
        for item in targets
        if item["status"] in reviewable_statuses and item["review_status"] is None
    ]
    by_action: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for item in backlog:
        action = str(item["recommended_action"] or "unknown")
        status = str(item["status"] or "unknown")
        by_action[action] = by_action.get(action, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
    return {
        "total": len(backlog),
        "by_recommended_action": by_action,
        "by_status": by_status,
        "target_ids": [item["target_id"] for item in backlog],
        "domains": [item["domain"] for item in backlog],
    }


def _run_source_quality_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        use_case = get_default_use_case(str(case.get("use_case") or "company_osint"))
        classifier = SourceQualityClassifier.from_source_policy(use_case.source_policy)
        result = classifier.classify(_search_result(case))
        actual = {
            "source_type": result.source_type.value,
            "action": result.recommended_action.value,
            "score": result.score,
        }
        expected = {
            "source_type": case["expected_source_type"],
            "action": case["expected_action"],
        }
        results.append(_case_result(case["id"], actual, expected))
    return _section_result(results)


def _run_rating_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        use_case = get_default_use_case(str(case["use_case"]))
        rating = RatingEngine(
            config=RatingConfig(),
            ai_provider=_ai_provider(case),
        ).rate(
            _target(case),
            _search_profile(case),
            _evidence(case),
            use_case=use_case,
        )
        actual = {
            "recommended_action": rating.recommended_action.value,
            "rating_status": rating.rating_status,
            "rule_score": rating.rule_score,
            "ai_score": rating.ai_score,
            "confidence": rating.confidence,
            "risk_types": sorted(
                {
                    str(risk.get("type"))
                    for risk in rating.risks
                    if isinstance(risk, dict) and risk.get("type")
                }
            ),
        }
        expected = {
            "recommended_action": case["expected_action"],
            "rating_status": case["expected_status"],
        }
        if "expected_risk_types" in case:
            expected["risk_types"] = sorted(case["expected_risk_types"])
        results.append(_case_result(case["id"], actual, expected))
    return _section_result(results)


def _run_draft_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        use_case = get_default_use_case(str(case["use_case"]))
        target = _target(case)
        rating = RatingResult(
            target_id=target.id or 1,
            recommended_action=RecommendedAction(case["rating_action"]),
            rule_score=int(case.get("rule_score", 80)),
            ai_score=case.get("ai_score", 80),
            confidence=float(case.get("confidence", 0.75)),
            rating_status=str(case.get("rating_status") or "use_case_rated"),
            rating_version="eval-rating-v1",
        )
        expected_status = str(case["expected_status"])
        try:
            draft = DraftEngine().create_draft(
                profile=_profile(case),
                target=target,
                rating=rating,
                evidence=_evidence(case),
                draft_policy=use_case.draft_policy,
            )
            actual = {
                "status": "generated",
                "draft_type": draft.draft_type,
                "claim_ref_count": len(draft.used_context.get("claim_refs", [])),
                "body_contains": {
                    value: value in draft.body
                    for value in case.get("required_body_contains", [])
                },
                "body_excludes": {
                    value: value not in draft.body
                    for value in case.get("forbidden_body_contains", [])
                },
            }
        except DraftSkippedError as exc:
            actual = {
                "status": "skipped",
                "error": str(exc),
            }
        expected: dict[str, Any] = {"status": expected_status}
        if expected_status == "generated":
            expected["draft_type"] = case["expected_draft_type"]
            if "expected_claim_ref_count" in case:
                expected["claim_ref_count"] = case["expected_claim_ref_count"]
            expected["body_contains"] = {
                value: True for value in case.get("required_body_contains", [])
            }
            expected["body_excludes"] = {
                value: True for value in case.get("forbidden_body_contains", [])
            }
        results.append(_case_result(case["id"], actual, expected))
    return _section_result(results)


def _run_review_feedback_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for case in cases:
        actual = {
            "recommended_action": case.get("actual_action"),
            "review_status": case.get("review_status"),
            "rating_status": case.get("rating_status"),
        }
        expected = {
            "recommended_action": case["expected_action"],
        }
        result = _case_result(str(case["id"]), actual, expected)
        if not result["passed"]:
            result["triage"] = _review_feedback_triage(case, actual, expected)
        results.append(result)
    section = _section_result(results)
    triage_items = [
        result["triage"]
        for result in results
        if not result["passed"] and "triage" in result
    ]
    section["conflict_summary"] = _review_conflict_summary(triage_items)
    section["action_items"] = triage_items
    return section


def _review_feedback_triage(
    case: dict[str, Any],
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    review_status = str(case.get("review_status") or "")
    actual_action = str(actual.get("recommended_action") or "")
    expected_action = str(expected.get("recommended_action") or "")
    conflict_type, severity, suggested_action = _review_conflict_policy(
        review_status,
        actual_action,
        expected_action,
    )
    return {
        "case_id": case.get("id"),
        "domain": case.get("domain"),
        "review_status": review_status,
        "actual_action": actual_action,
        "expected_action": expected_action,
        "conflict_type": conflict_type,
        "severity": severity,
        "suggested_action": suggested_action,
        "rationale": _review_conflict_rationale(case),
    }


def _review_conflict_policy(
    review_status: str,
    actual_action: str,
    expected_action: str,
) -> tuple[str, str, str]:
    if review_status == "blacklisted" and actual_action != "skip":
        return (
            "blacklist_miss",
            "high",
            "add domain/source block or tighten source policy before rating",
        )
    if review_status == "rejected" and actual_action == "draft":
        return (
            "false_positive_draft",
            "high",
            "add a rating eval case or tighten draft threshold/criteria",
        )
    if review_status == "rejected" and actual_action == "review":
        return (
            "false_positive_review",
            "medium",
            "inspect rating risks and decide whether skip threshold should change",
        )
    if review_status == "approved" and actual_action != "draft":
        return (
            "false_negative",
            "medium",
            "add a positive rating eval case or relax criteria/thresholds",
        )
    return (
        "review_mismatch",
        "low",
        f"inspect review feedback expected {expected_action} but got {actual_action}",
    )


def _review_conflict_rationale(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "rating_status": case.get("rating_status"),
        "rule_score": case.get("rule_score"),
        "ai_score": case.get("ai_score"),
        "confidence": case.get("confidence"),
        "risk_types": list(case.get("risk_types") or []),
        "evidence_count": case.get("evidence_count"),
        "draft_count": case.get("draft_count"),
        "source": case.get("source"),
        "use_case": case.get("use_case"),
    }


def _review_conflict_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for item in items:
        conflict_type = str(item.get("conflict_type") or "unknown")
        severity = str(item.get("severity") or "unknown")
        by_type[conflict_type] = by_type.get(conflict_type, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {
        "total": len(items),
        "by_type": by_type,
        "by_severity": by_severity,
    }


def _case_result(
    case_id: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    failures = [
        f"{key}: expected {expected_value!r}, got {actual.get(key)!r}"
        for key, expected_value in expected.items()
        if actual.get(key) != expected_value
    ]
    return {
        "id": case_id,
        "passed": not failures,
        "expected": expected,
        "actual": actual,
        "failures": failures,
    }


def _section_result(results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for result in results if result["passed"])
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": _ratio(passed, total),
        "failures": [result for result in results if not result["passed"]],
    }


def _load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path)
    with fixture_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("evaluation fixture must contain a JSON object")
    return payload


def _review_feedback_cases(store: SQLiteStore, *, limit: int) -> list[dict[str, Any]]:
    rows = store.connection.execute(
        """
        WITH latest_review AS (
            SELECT target_id, MAX(id) AS log_id
            FROM target_status_log
            WHERE phase = 'review'
              AND to_status IN ('approved', 'rejected', 'blacklisted')
            GROUP BY target_id
        )
        SELECT
            log.id AS review_log_id,
            log.to_status AS review_status,
            log.reason AS review_reason,
            log.created_at AS review_created_at,
            targets.id AS target_id,
            targets.domain,
            targets.base_url,
            targets.source,
            scores.id AS score_id,
            scores.recommended_action,
            scores.rating_status,
            scores.rule_score,
            scores.ai_score,
            scores.confidence,
            scores.risks_json,
            use_cases.slug AS use_case_slug,
            use_cases.name AS use_case_name,
            (
                SELECT COUNT(*)
                FROM evidence
                WHERE evidence.target_id = targets.id
            ) AS evidence_count,
            (
                SELECT COUNT(*)
                FROM action_drafts
                WHERE action_drafts.target_id = targets.id
            ) AS draft_count
        FROM latest_review
        INNER JOIN target_status_log AS log
            ON log.id = latest_review.log_id
        INNER JOIN targets
            ON targets.id = latest_review.target_id
        LEFT JOIN target_scores AS scores
            ON scores.id = (
                SELECT id
                FROM target_scores
                WHERE target_scores.target_id = targets.id
                ORDER BY id DESC
                LIMIT 1
            )
        LEFT JOIN pipeline_runs
            ON pipeline_runs.id = COALESCE(scores.pipeline_run_id, log.pipeline_run_id)
        LEFT JOIN search_profiles
            ON search_profiles.id = pipeline_runs.search_profile_id
        LEFT JOIN use_cases
            ON use_cases.id = search_profiles.use_case_id
        ORDER BY log.id DESC
        LIMIT ?
        """,
        (max(1, limit),),
    ).fetchall()
    cases = []
    for row in rows:
        review_status = str(row["review_status"])
        actual_action = str(row["recommended_action"] or "review")
        cases.append(
            {
                "id": f"local_review_{row['target_id']}_{row['review_log_id']}",
                "target_id": row["target_id"],
                "domain": row["domain"],
                "base_url": row["base_url"],
                "source": row["source"],
                "use_case": row["use_case_slug"] or "unknown",
                "use_case_name": row["use_case_name"],
                "review_status": review_status,
                "review_reason": row["review_reason"],
                "review_created_at": row["review_created_at"],
                "actual_action": actual_action,
                "expected_action": _REVIEW_EXPECTED_ACTION[review_status],
                "rating_status": row["rating_status"],
                "rule_score": row["rule_score"],
                "ai_score": row["ai_score"],
                "confidence": row["confidence"],
                "risk_types": _risk_types(row["risks_json"]),
                "evidence_count": row["evidence_count"],
                "draft_count": row["draft_count"],
            }
        )
    return cases


def _risk_types(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        risks = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(risks, list):
        return []
    return sorted(
        {
            str(risk.get("type"))
            for risk in risks
            if isinstance(risk, dict) and risk.get("type")
        }
    )


def _search_result(case: dict[str, Any]) -> SearchResult:
    metadata = dict(case.get("metadata") or {})
    if case.get("provider_rank") is not None:
        metadata["provider_rank"] = case["provider_rank"]
    return SearchResult(
        url=str(case["url"]),
        title=str(case.get("title") or ""),
        snippet=str(case.get("snippet") or ""),
        metadata=metadata,
    )


def _profile(case: dict[str, Any]) -> Profile:
    return Profile(
        id=1,
        name=str(case.get("profile_name") or "Eval Profile"),
        draft_language=str(case.get("draft_language") or "de"),
    )


def _search_profile(case: dict[str, Any]) -> SearchProfile:
    search = case.get("search_profile") or {}
    return SearchProfile(
        id=1,
        profile_id=1,
        name=str(search.get("name") or case.get("id") or "Eval Search"),
        roles=_tuple(search.get("roles")),
        regions=_tuple(search.get("regions")),
        tech_keywords=_tuple(search.get("tech_keywords")),
        industry_keywords=_tuple(search.get("industry_keywords")),
        exclude_keywords=_tuple(search.get("exclude_keywords")),
        attributes=dict(search.get("attributes") or {}),
        draft_language=str(search.get("draft_language") or "de"),
    )


def _target(case: dict[str, Any]) -> Target:
    url = str(case.get("url") or case.get("base_url") or "https://example.com")
    return Target(
        id=int(case.get("target_id") or 1),
        domain=str(case.get("domain") or domain_from_url(url)),
        base_url=url,
        source=str(case.get("source") or "eval"),
        status=TargetStatus.DRAFT_PENDING,
        metadata=dict(case.get("target_metadata") or {}),
    )


def _evidence(case: dict[str, Any]) -> list[Evidence]:
    target_id = int(case.get("target_id") or 1)
    evidence_items = []
    for index, item in enumerate(case.get("evidence") or [], start=1):
        evidence_items.append(
            Evidence(
                id=index,
                target_id=target_id,
                source_url=str(item["source_url"]),
                text=str(item["text"]),
                context_type=str(item.get("context_type") or "page"),
                priority=int(item.get("priority", 50)),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return evidence_items


def _ai_provider(case: dict[str, Any]) -> FakeAIRatingProvider:
    ai_response = case.get("ai_response")
    if not isinstance(ai_response, dict):
        return FakeAIRatingProvider()
    return FakeAIRatingProvider(
        AIRatingResponse(
            ai_score=int(ai_response["ai_score"]),
            confidence=float(ai_response["confidence"]),
            recommended_action=RecommendedAction(ai_response["recommended_action"]),
            reasons=list(ai_response.get("reasons") or []),
            risks=list(ai_response.get("risks") or []),
            model_name=str(ai_response.get("model_name") or "eval-fake-ai"),
        )
    )


def _tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _ratio(passed: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(passed / total, 3)
