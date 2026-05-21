"""Query fanout for the LeadEngine."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from target_radar.domain import SearchProfile


@dataclass(frozen=True, slots=True)
class QueryCandidate:
    text: str
    query_hash: str
    query_template: str
    template_set: str
    score: int


class QueryBuilder:
    """Build short, deduplicated queries from a search profile."""

    def build(
        self,
        search_profile: SearchProfile,
        *,
        template_set: str | None = None,
        limit: int | None = None,
    ) -> list[QueryCandidate]:
        selected_template_set = template_set or self._infer_template_set(search_profile)
        rendered = self._render(search_profile, selected_template_set)

        seen: set[str] = set()
        candidates: list[QueryCandidate] = []
        for text, template, score in rendered:
            normalized = normalize_query(text)
            if not normalized:
                continue
            query_hash = hash_query("generic", normalized)
            if query_hash in seen:
                continue
            seen.add(query_hash)
            candidates.append(
                QueryCandidate(
                    text=normalized,
                    query_hash=query_hash,
                    query_template=template,
                    template_set=selected_template_set,
                    score=score,
                )
            )
            if limit is not None and len(candidates) >= limit:
                break

        return candidates

    def _infer_template_set(self, search_profile: SearchProfile) -> str:
        student_terms = ("werkstudent", "praktikum", "student", "abschlussarbeit")
        haystack = " ".join(search_profile.roles).lower()
        if any(term in haystack for term in student_terms):
            return "application_student"
        return "application_general"

    def _render(
        self,
        search_profile: SearchProfile,
        template_set: str,
    ) -> list[tuple[str, str, int]]:
        roles = search_profile.roles or ("",)
        regions = search_profile.regions or ("",)
        techs = search_profile.tech_keywords or ("",)
        industries = search_profile.industry_keywords or ("",)
        manual_queries = (search_profile.manual_query,) if search_profile.manual_query else ()

        rendered: list[tuple[str, str, int]] = []
        for query in manual_queries:
            rendered.append((query, "manual_query", 100))

        for role in roles:
            for region in regions:
                if role and region:
                    rendered.append((f"{role} {region} Karriere", "{role} {region} Karriere", 90))
                    rendered.append((f"{role} {region} Jobs", "{role} {region} Jobs", 80))
            for tech in techs:
                if role and tech:
                    rendered.append((f"{role} {tech} Karriere", "{role} {tech} Karriere", 75))

        for role in roles:
            for tech in techs:
                for region in regions:
                    if role and tech and region:
                        rendered.append((f"{role} {tech} {region}", "{role} {tech} {region}", 95))

        for role in roles:
            for industry in industries:
                for region in regions:
                    if role and industry and region:
                        rendered.append(
                            (
                                f"{role} {industry} {region}",
                                "{role} {industry} {region}",
                                70,
                            )
                        )

        if template_set == "application_student":
            for tech in techs:
                for industry in industries:
                    for region in regions:
                        if tech and industry and region:
                            rendered.append(
                                (
                                    f"{tech} {industry} {region}",
                                    "{tech} {industry} {region}",
                                    55,
                                )
                            )

        return sorted(rendered, key=lambda item: item[2], reverse=True)


def normalize_query(query: str) -> str:
    return " ".join(query.split()).strip()


def hash_query(provider: str, normalized_query: str) -> str:
    payload = f"{provider}:{normalized_query.lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
