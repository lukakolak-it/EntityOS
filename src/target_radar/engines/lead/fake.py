"""Deterministic LeadEngine implementation for tests and local demos."""

from __future__ import annotations

from dataclasses import dataclass, field

from target_radar.domain import SearchProfile, TargetCandidate


@dataclass(slots=True)
class FakeLeadEngine:
    """Return deterministic candidates without network access."""

    candidates: list[TargetCandidate] = field(default_factory=list)

    def discover(
        self,
        search_profile: SearchProfile,
        *,
        limit: int | None = None,
    ) -> list[TargetCandidate]:
        if self.candidates:
            results = list(self.candidates)
        else:
            results = self._default_candidates(search_profile)

        if limit is not None:
            return results[:limit]
        return results

    def _default_candidates(self, search_profile: SearchProfile) -> list[TargetCandidate]:
        role = _slug(search_profile.roles[0] if search_profile.roles else "target")
        region = _slug(search_profile.regions[0] if search_profile.regions else "local")
        tech = _slug(
            search_profile.tech_keywords[0]
            if search_profile.tech_keywords
            else "technology"
        )

        return [
            TargetCandidate(
                url=f"https://{role}-{region}.example/careers",
                source="fake",
                title=f"{search_profile.name} Careers",
                snippet="Deterministic fake discovery result.",
            ),
            TargetCandidate(
                url=f"https://{tech}-{region}.example/jobs",
                source="fake",
                title=f"{tech} jobs",
                snippet="Second deterministic fake discovery result.",
            ),
        ]


def _slug(value: str) -> str:
    cleaned = "".join(
        char.lower() if char.isalnum() else "-"
        for char in value.strip()
        if char.isalnum() or char.isspace() or char in "-_"
    )
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "target"
