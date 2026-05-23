"""Query fanout for the LeadEngine."""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import dataclass

from target_radar.domain import SearchProfile
from target_radar.use_cases import UseCaseConfig, template_variables


_NEGATIVE_TOKEN_RE = re.compile(r'-(?:"[^"]+"|\S+)')


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
        use_case: UseCaseConfig | None = None,
    ) -> list[QueryCandidate]:
        if use_case is not None:
            selected_template_set = template_set or use_case.query_policy.default_template_set
            rendered = self._render_use_case(search_profile, use_case)
        else:
            selected_template_set = template_set or self._infer_template_set(search_profile)
            rendered = self._render(search_profile, selected_template_set)

        seen: set[str] = set()
        candidates: list[QueryCandidate] = []
        for text, template, score in rendered:
            normalized = normalize_query(text)
            if not normalized:
                continue
            if template != "manual_query":
                normalized = _append_exclusions(
                    normalized,
                    _exclude_terms(search_profile, use_case),
                )
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

    def _render_use_case(
        self,
        search_profile: SearchProfile,
        use_case: UseCaseConfig,
    ) -> list[tuple[str, str, int]]:
        rendered: list[tuple[str, str, int]] = []
        if search_profile.manual_query:
            rendered.append((search_profile.manual_query, "manual_query", 100))

        values_by_field = _search_profile_values(search_profile)
        for index, template in enumerate(use_case.query_policy.templates):
            variables = sorted(template_variables(template))
            value_sets: list[tuple[str, tuple[str, ...]]] = []
            for variable in variables:
                field_key = use_case.query_policy.variable_map.get(variable, variable)
                values = values_by_field.get(field_key, ())
                if not values:
                    break
                value_sets.append((variable, values))
            else:
                score = _use_case_template_score(template, index)
                for values in itertools.product(*(item[1] for item in value_sets)):
                    context = {
                        variable: value
                        for (variable, _field_values), value in zip(value_sets, values)
                    }
                    rendered.append((template.format(**context), template, score))

        return sorted(rendered, key=lambda item: item[2], reverse=True)


def normalize_query(query: str) -> str:
    return " ".join(query.split()).strip()


def hash_query(provider: str, normalized_query: str) -> str:
    payload = f"{provider}:{normalized_query.lower()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _search_profile_values(search_profile: SearchProfile) -> dict[str, tuple[str, ...]]:
    values: dict[str, tuple[str, ...]] = {
        "roles": search_profile.roles,
        "regions": search_profile.regions,
        "tech_keywords": search_profile.tech_keywords,
        "industry_keywords": search_profile.industry_keywords,
        "exclude_keywords": search_profile.exclude_keywords,
    }
    for key, value in search_profile.attributes.items():
        values[key] = _coerce_values(value)

    values.setdefault("topics", search_profile.roles)
    values.setdefault("industries", search_profile.industry_keywords)
    return values


def _coerce_values(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _exclude_terms(
    search_profile: SearchProfile,
    use_case: UseCaseConfig | None,
) -> tuple[str, ...]:
    terms = list(search_profile.exclude_keywords)
    if use_case is not None:
        terms.extend(use_case.query_policy.exclude_terms)
    return tuple(_dedupe_preserve_order(terms))


def _append_exclusions(query: str, exclude_terms: tuple[str, ...]) -> str:
    existing = {token.casefold() for token in _negative_query_tokens(query)}
    additions: list[str] = []
    for term in exclude_terms:
        token = _negative_query_token(term)
        if not token or token.casefold() in existing:
            continue
        additions.append(token)
        existing.add(token.casefold())
    return normalize_query(" ".join((query, *additions)))


def _negative_query_token(term: str) -> str:
    clean = normalize_query(term).lstrip("-")
    if not clean:
        return ""
    if any(char.isspace() for char in clean):
        return f'-"{clean}"'
    return f"-{clean}"


def _negative_query_tokens(query: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in _NEGATIVE_TOKEN_RE.finditer(query))


def _dedupe_preserve_order(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        clean = normalize_query(str(value)).lstrip("-")
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return tuple(deduped)


def _use_case_template_score(template: str, index: int) -> int:
    variables = template_variables(template)
    score = 100 - index * 5
    if {"role", "tech", "region"} <= variables:
        score += 20
    if {"topic", "region"} <= variables:
        score += 10
    lower = template.lower()
    if any(token in lower for token in ("kontakt", "impressum", "services")):
        score += 4
    if "karriere" in template.lower():
        score += 5
    return score
