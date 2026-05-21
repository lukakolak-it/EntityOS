"""Target import and dedupe for LeadEngine candidates."""

from __future__ import annotations

from dataclasses import dataclass

from target_radar.domain import (
    ImportStatus,
    LeadResultStatus,
    Target,
    TargetCandidate,
    TargetStatus,
    normalize_domain,
)
from target_radar.storage import SQLiteStore


@dataclass(frozen=True, slots=True)
class TargetImportResult:
    candidate: TargetCandidate
    status: ImportStatus
    target: Target | None = None
    reason: str | None = None


class TargetImporter:
    """Import normalized candidates into local targets."""

    def __init__(
        self,
        store: SQLiteStore,
        *,
        blocked_domains: set[str] | None = None,
        blacklisted_domains: set[str] | None = None,
    ) -> None:
        self.store = store
        self.blocked_domains = {
            normalize_domain(domain) for domain in (blocked_domains or set())
        }
        self.blacklisted_domains = {
            normalize_domain(domain) for domain in (blacklisted_domains or set())
        }

    def import_candidates(
        self,
        candidates: list[TargetCandidate],
    ) -> list[TargetImportResult]:
        seen_domains: set[str] = set()
        results: list[TargetImportResult] = []

        for candidate in candidates:
            domain = candidate.domain
            if domain is None:
                results.append(
                    TargetImportResult(
                        candidate=candidate,
                        status=ImportStatus.INVALID,
                        reason="missing domain",
                    )
                )
                continue

            if domain in seen_domains:
                results.append(
                    TargetImportResult(
                        candidate=candidate,
                        status=ImportStatus.DUPLICATE_INPUT,
                        reason="domain already present in import batch",
                    )
                )
                continue
            seen_domains.add(domain)

            if candidate.status == LeadResultStatus.BLOCKED_SOURCE:
                results.append(
                    TargetImportResult(
                        candidate=candidate,
                        status=ImportStatus.BLOCKED_SOURCE,
                        reason="candidate source is blocked",
                    )
                )
                continue

            if domain in self.blocked_domains:
                results.append(
                    TargetImportResult(
                        candidate=candidate,
                        status=ImportStatus.BLOCKED_SOURCE,
                        reason="domain is denylisted",
                    )
                )
                continue

            if candidate.status == LeadResultStatus.BLACKLISTED:
                results.append(
                    TargetImportResult(
                        candidate=candidate,
                        status=ImportStatus.BLACKLISTED,
                        reason="candidate is blacklisted",
                    )
                )
                continue

            if domain in self.blacklisted_domains:
                results.append(
                    TargetImportResult(
                        candidate=candidate,
                        status=ImportStatus.BLACKLISTED,
                        reason="domain is user blacklisted",
                    )
                )
                continue

            existing = self.store.get_target_by_domain(domain)
            if existing is not None:
                results.append(
                    TargetImportResult(
                        candidate=candidate,
                        status=ImportStatus.EXISTING,
                        target=existing,
                    )
                )
                continue

            target = self.store.create_target(
                Target(
                    domain=domain,
                    base_url=candidate.url,
                    source=candidate.source,
                    status=TargetStatus.IMPORTED,
                    metadata={
                        "title": candidate.title,
                        "snippet": candidate.snippet,
                    },
                )
            )
            results.append(
                TargetImportResult(
                    candidate=candidate,
                    status=ImportStatus.IMPORTED,
                    target=target,
                )
            )

        return results
