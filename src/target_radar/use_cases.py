"""Use case schema and default templates."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class UseCaseStatus(StrEnum):
    TEMPLATE = "template"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class AttributeFieldType(StrEnum):
    TEXT = "text"
    LIST = "list"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


class RatingEvaluation(StrEnum):
    RULES = "rules"
    LLM = "llm"
    HYBRID = "hybrid"


KNOWN_SOURCE_TYPES = frozenset(
    {
        "official_site",
        "company_site",
        "directory",
        "job_board",
        "social",
        "repository",
        "news",
        "registry",
        "marketplace",
        "unknown",
    }
)
KNOWN_RULE_SETS = frozenset(
    {
        "role_keyword_match",
        "tech_keyword_match",
        "region_keyword_match",
        "source_quality",
        "contactability",
        "evidence_quality",
    }
)
KNOWN_EVIDENCE_TYPES = frozenset(
    {
        "target_homepage",
        "target_career",
        "target_contact",
        "target_about",
        "target_page",
        "context_directory",
        "context_news",
        "context_registry",
        "context_repository",
        "context_source",
    }
)
KNOWN_DRAFT_TYPES = frozenset({"application_email", "research_summary", "none"})
DRAFT_OUTPUT_SCHEMAS: dict[str, tuple[str, ...]] = {
    "application_email": ("subject", "body"),
    "research_summary": (
        "title",
        "summary",
        "key_findings",
        "evidence",
        "risks_or_uncertainties",
        "next_steps",
    ),
    "none": (),
}
KNOWN_REVIEW_ACTIONS = frozenset({"approve", "reject", "blacklist"})
KNOWN_REVIEW_SCOPES = frozenset({"all", "use_case"})
KNOWN_LLM_MODES = frozenset({"off", "light", "heavy"})


@dataclass(frozen=True, slots=True)
class AttributeField:
    key: str
    label: str
    type: AttributeFieldType | str = AttributeFieldType.TEXT
    required: bool = False
    help_text: str | None = None
    default: Any = None
    options: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _ensure_identifier(self.key, "field.key"))
        object.__setattr__(self, "label", _ensure_non_empty(self.label, "field.label"))
        object.__setattr__(self, "type", AttributeFieldType(self.type))
        object.__setattr__(self, "options", _clean_tuple(self.options))
        if self.type == AttributeFieldType.SELECT and not self.options:
            raise ValueError(f"field {self.key!r} of type select needs options")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AttributeField:
        return cls(
            key=str(value.get("key", "")),
            label=str(value.get("label", "")),
            type=value.get("type", AttributeFieldType.TEXT),
            required=bool(value.get("required", False)),
            help_text=_optional_str(value.get("help_text")),
            default=value.get("default"),
            options=_tuple_from(value.get("options", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "type": self.type.value,
            "required": self.required,
        }
        if self.help_text is not None:
            data["help_text"] = self.help_text
        if self.default is not None:
            data["default"] = self.default
        if self.options:
            data["options"] = list(self.options)
        return data


@dataclass(frozen=True, slots=True)
class AttributeSchema:
    fields: tuple[AttributeField, ...]

    def __post_init__(self) -> None:
        fields = tuple(self.fields)
        if not fields:
            raise ValueError("attribute_schema.fields must not be empty")
        seen: set[str] = set()
        for item in fields:
            if item.key in seen:
                raise ValueError(f"duplicate attribute field: {item.key}")
            seen.add(item.key)
        object.__setattr__(self, "fields", fields)

    @property
    def field_keys(self) -> frozenset[str]:
        return frozenset(field.key for field in self.fields)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AttributeSchema:
        return cls(
            fields=tuple(
                item if isinstance(item, AttributeField) else AttributeField.from_dict(item)
                for item in value.get("fields", ())
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {"fields": [field.to_dict() for field in self.fields]}


@dataclass(frozen=True, slots=True)
class QueryPolicy:
    templates: tuple[str, ...]
    default_template_set: str
    request_budget_default: int = 25
    results_per_query_default: int = 5
    variable_map: dict[str, str] = field(default_factory=dict)
    exclude_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        templates = _clean_tuple(self.templates)
        if not templates:
            raise ValueError("query_policy.templates must not be empty")
        object.__setattr__(self, "templates", templates)
        object.__setattr__(
            self,
            "default_template_set",
            _ensure_identifier(self.default_template_set, "query_policy.default_template_set"),
        )
        if self.request_budget_default <= 0:
            raise ValueError("query_policy.request_budget_default must be positive")
        if self.results_per_query_default <= 0:
            raise ValueError("query_policy.results_per_query_default must be positive")
        clean_map: dict[str, str] = {}
        for key, target in dict(self.variable_map).items():
            clean_map[_ensure_identifier(key, "query_policy.variable_map key")] = (
                _ensure_identifier(target, f"query_policy.variable_map[{key!r}]")
            )
        object.__setattr__(self, "variable_map", clean_map)
        object.__setattr__(self, "exclude_terms", _clean_tuple(self.exclude_terms))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> QueryPolicy:
        return cls(
            templates=_tuple_from(value.get("templates", ())),
            default_template_set=str(value.get("default_template_set", "")),
            request_budget_default=int(value.get("request_budget_default", 25)),
            results_per_query_default=int(value.get("results_per_query_default", 5)),
            variable_map=dict(value.get("variable_map", {})),
            exclude_terms=_tuple_from(value.get("exclude_terms", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_template_set": self.default_template_set,
            "request_budget_default": self.request_budget_default,
            "results_per_query_default": self.results_per_query_default,
            "variable_map": dict(self.variable_map),
            "exclude_terms": list(self.exclude_terms),
            "templates": list(self.templates),
        }


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    preferred_source_types: tuple[str, ...] = ()
    context_source_types: tuple[str, ...] = ()
    blocked_source_types: tuple[str, ...] = ()
    blocked_domains: tuple[str, ...] = ()
    preferred_domains: tuple[str, ...] = ()
    relevant_path_tokens: tuple[str, ...] = ()
    listing_path_tokens: tuple[str, ...] = ()
    import_threshold: int = 65
    review_threshold: int = 35

    def __post_init__(self) -> None:
        object.__setattr__(self, "preferred_source_types", _clean_tuple(self.preferred_source_types))
        object.__setattr__(self, "context_source_types", _clean_tuple(self.context_source_types))
        object.__setattr__(self, "blocked_source_types", _clean_tuple(self.blocked_source_types))
        object.__setattr__(self, "blocked_domains", _clean_tuple(self.blocked_domains))
        object.__setattr__(self, "preferred_domains", _clean_tuple(self.preferred_domains))
        object.__setattr__(
            self,
            "relevant_path_tokens",
            _clean_tuple(self.relevant_path_tokens),
        )
        object.__setattr__(
            self,
            "listing_path_tokens",
            _clean_tuple(self.listing_path_tokens),
        )
        if self.import_threshold < 0 or self.import_threshold > 100:
            raise ValueError("source_policy.import_threshold must be between 0 and 100")
        if self.review_threshold < 0 or self.review_threshold > 100:
            raise ValueError("source_policy.review_threshold must be between 0 and 100")
        if self.review_threshold > self.import_threshold:
            raise ValueError("source_policy.review_threshold must not exceed import_threshold")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourcePolicy:
        return cls(
            preferred_source_types=_tuple_from(value.get("preferred_source_types", ())),
            context_source_types=_tuple_from(value.get("context_source_types", ())),
            blocked_source_types=_tuple_from(value.get("blocked_source_types", ())),
            blocked_domains=_tuple_from(value.get("blocked_domains", ())),
            preferred_domains=_tuple_from(value.get("preferred_domains", ())),
            relevant_path_tokens=_tuple_from(value.get("relevant_path_tokens", ())),
            listing_path_tokens=_tuple_from(value.get("listing_path_tokens", ())),
            import_threshold=int(value.get("import_threshold", 65)),
            review_threshold=int(value.get("review_threshold", 35)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_source_types": list(self.preferred_source_types),
            "context_source_types": list(self.context_source_types),
            "blocked_source_types": list(self.blocked_source_types),
            "blocked_domains": list(self.blocked_domains),
            "preferred_domains": list(self.preferred_domains),
            "relevant_path_tokens": list(self.relevant_path_tokens),
            "listing_path_tokens": list(self.listing_path_tokens),
            "import_threshold": self.import_threshold,
            "review_threshold": self.review_threshold,
        }


@dataclass(frozen=True, slots=True)
class RatingCriterion:
    key: str
    label: str
    weight: int
    evaluation: RatingEvaluation | str
    rule_set: str | None = None
    llm_instruction: str | None = None
    evidence_types: tuple[str, ...] = ()
    min_evidence_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _ensure_identifier(self.key, "criterion.key"))
        object.__setattr__(self, "label", _ensure_non_empty(self.label, "criterion.label"))
        if self.weight <= 0:
            raise ValueError(f"criterion {self.key!r} weight must be positive")
        object.__setattr__(self, "evaluation", RatingEvaluation(self.evaluation))
        object.__setattr__(self, "rule_set", _optional_identifier(self.rule_set))
        object.__setattr__(self, "llm_instruction", _optional_non_empty(self.llm_instruction))
        object.__setattr__(self, "evidence_types", _clean_tuple(self.evidence_types))
        if self.min_evidence_count < 0:
            raise ValueError(f"criterion {self.key!r} min_evidence_count must not be negative")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RatingCriterion:
        return cls(
            key=str(value.get("key", "")),
            label=str(value.get("label", "")),
            weight=int(value.get("weight", 0)),
            evaluation=value.get("evaluation", ""),
            rule_set=_optional_str(value.get("rule_set")),
            llm_instruction=_optional_str(value.get("llm_instruction")),
            evidence_types=_tuple_from(value.get("evidence_types", ())),
            min_evidence_count=int(value.get("min_evidence_count", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "weight": self.weight,
            "evaluation": self.evaluation.value,
        }
        if self.rule_set is not None:
            data["rule_set"] = self.rule_set
        if self.llm_instruction is not None:
            data["llm_instruction"] = self.llm_instruction
        if self.evidence_types:
            data["evidence_types"] = list(self.evidence_types)
        if self.min_evidence_count:
            data["min_evidence_count"] = self.min_evidence_count
        return data


@dataclass(frozen=True, slots=True)
class RatingPolicy:
    criteria: tuple[RatingCriterion, ...]
    llm_mode: str = "light"
    min_score_for_review: int = 50
    min_score_for_draft: int = 70

    def __post_init__(self) -> None:
        criteria = tuple(self.criteria)
        if not criteria:
            raise ValueError("rating_policy.criteria must not be empty")
        seen: set[str] = set()
        for item in criteria:
            if item.key in seen:
                raise ValueError(f"duplicate rating criterion: {item.key}")
            seen.add(item.key)
        object.__setattr__(self, "criteria", criteria)
        object.__setattr__(self, "llm_mode", _ensure_known(self.llm_mode, KNOWN_LLM_MODES, "llm_mode"))
        if self.min_score_for_review < 0 or self.min_score_for_review > 100:
            raise ValueError("rating_policy.min_score_for_review must be between 0 and 100")
        if self.min_score_for_draft < 0 or self.min_score_for_draft > 100:
            raise ValueError("rating_policy.min_score_for_draft must be between 0 and 100")
        if self.min_score_for_review > self.min_score_for_draft:
            raise ValueError("rating_policy.min_score_for_review must not exceed min_score_for_draft")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RatingPolicy:
        return cls(
            criteria=tuple(
                item if isinstance(item, RatingCriterion) else RatingCriterion.from_dict(item)
                for item in value.get("criteria", ())
            ),
            llm_mode=str(value.get("llm_mode", "light")),
            min_score_for_review=int(value.get("min_score_for_review", 50)),
            min_score_for_draft=int(value.get("min_score_for_draft", 70)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm_mode": self.llm_mode,
            "min_score_for_review": self.min_score_for_review,
            "min_score_for_draft": self.min_score_for_draft,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
        }


@dataclass(frozen=True, slots=True)
class DraftPolicy:
    draft_type: str
    language: str = "de"
    max_length_chars: int = 3500
    required_sections: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()
    include_sources: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "draft_type", _ensure_known(self.draft_type, KNOWN_DRAFT_TYPES, "draft_type"))
        object.__setattr__(self, "language", _ensure_non_empty(self.language, "draft_policy.language"))
        if self.max_length_chars <= 0:
            raise ValueError("draft_policy.max_length_chars must be positive")
        object.__setattr__(self, "required_sections", _clean_tuple(self.required_sections))
        object.__setattr__(self, "forbidden_claims", _clean_tuple(self.forbidden_claims))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> DraftPolicy:
        return cls(
            draft_type=str(value.get("draft_type", "")),
            language=str(value.get("language", "de")),
            max_length_chars=int(value.get("max_length_chars", 3500)),
            required_sections=_tuple_from(value.get("required_sections", ())),
            forbidden_claims=_tuple_from(value.get("forbidden_claims", ())),
            include_sources=bool(value.get("include_sources", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft_type": self.draft_type,
            "language": self.language,
            "max_length_chars": self.max_length_chars,
            "required_sections": list(self.required_sections),
            "forbidden_claims": list(self.forbidden_claims),
            "include_sources": self.include_sources,
        }


@dataclass(frozen=True, slots=True)
class ReviewPolicy:
    actions: tuple[str, ...]
    columns: tuple[str, ...] = ("domain", "score", "recommended_action")
    default_scope: str = "use_case"

    def __post_init__(self) -> None:
        actions = _clean_tuple(self.actions)
        if not actions:
            raise ValueError("review_policy.actions must not be empty")
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "columns", _clean_tuple(self.columns))
        object.__setattr__(
            self,
            "default_scope",
            _ensure_known(self.default_scope, KNOWN_REVIEW_SCOPES, "review_policy.default_scope"),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ReviewPolicy:
        return cls(
            actions=_tuple_from(value.get("actions", ())),
            columns=_tuple_from(value.get("columns", ("domain", "score", "recommended_action"))),
            default_scope=str(value.get("default_scope", "use_case")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_scope": self.default_scope,
            "actions": list(self.actions),
            "columns": list(self.columns),
        }


@dataclass(frozen=True, slots=True)
class UseCaseConfig:
    id: str
    name: str
    version: int
    attribute_schema: AttributeSchema
    query_policy: QueryPolicy
    source_policy: SourcePolicy
    rating_policy: RatingPolicy
    draft_policy: DraftPolicy
    review_policy: ReviewPolicy
    description: str = ""
    status: UseCaseStatus | str = UseCaseStatus.TEMPLATE
    created_from_template: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _ensure_identifier(self.id, "use_case.id"))
        object.__setattr__(self, "name", _ensure_non_empty(self.name, "use_case.name"))
        if self.version <= 0:
            raise ValueError("use_case.version must be positive")
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "status", UseCaseStatus(self.status))
        object.__setattr__(
            self,
            "created_from_template",
            _optional_identifier(self.created_from_template),
        )
        _validate_use_case(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> UseCaseConfig:
        return cls(
            id=str(value.get("id", "")),
            name=str(value.get("name", "")),
            version=int(value.get("version", 0)),
            description=str(value.get("description", "")),
            status=value.get("status", UseCaseStatus.TEMPLATE),
            created_from_template=_optional_str(value.get("created_from_template")),
            attribute_schema=AttributeSchema.from_dict(value.get("attribute_schema", {})),
            query_policy=QueryPolicy.from_dict(value.get("query_policy", {})),
            source_policy=SourcePolicy.from_dict(value.get("source_policy", {})),
            rating_policy=RatingPolicy.from_dict(value.get("rating_policy", {})),
            draft_policy=DraftPolicy.from_dict(value.get("draft_policy", {})),
            review_policy=ReviewPolicy.from_dict(value.get("review_policy", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "status": self.status.value,
            "attribute_schema": self.attribute_schema.to_dict(),
            "query_policy": self.query_policy.to_dict(),
            "source_policy": self.source_policy.to_dict(),
            "rating_policy": self.rating_policy.to_dict(),
            "draft_policy": self.draft_policy.to_dict(),
            "review_policy": self.review_policy.to_dict(),
        }
        if self.created_from_template is not None:
            data["created_from_template"] = self.created_from_template
        return data


def get_default_use_case(use_case_id: str) -> UseCaseConfig:
    try:
        return DEFAULT_USE_CASE_BY_ID[use_case_id]
    except KeyError as exc:
        raise ValueError(f"unknown default use case: {use_case_id}") from exc


def validate_use_case_config(use_case: UseCaseConfig | Mapping[str, Any]) -> UseCaseConfig:
    if isinstance(use_case, UseCaseConfig):
        _validate_use_case(use_case)
        return use_case
    return UseCaseConfig.from_dict(use_case)


def template_variables(template: str) -> frozenset[str]:
    variables: set[str] = set()
    try:
        parsed = string.Formatter().parse(template)
        for _literal, field_name, format_spec, conversion in parsed:
            if field_name is None:
                continue
            if format_spec or conversion:
                raise ValueError("format specs and conversions are not supported")
            variables.add(_ensure_identifier(field_name, f"query template variable {field_name!r}"))
    except ValueError as exc:
        raise ValueError(f"invalid query template {template!r}: {exc}") from exc
    return frozenset(variables)


def _validate_use_case(use_case: UseCaseConfig) -> None:
    field_keys = use_case.attribute_schema.field_keys
    _validate_query_policy(use_case.query_policy, field_keys)
    _validate_source_policy(use_case.source_policy)
    _validate_rating_policy(use_case.rating_policy)
    _validate_draft_policy(use_case.draft_policy)
    _validate_review_policy(use_case.review_policy)


def _validate_query_policy(query_policy: QueryPolicy, field_keys: frozenset[str]) -> None:
    for alias, target in query_policy.variable_map.items():
        if target not in field_keys:
            raise ValueError(f"query_policy.variable_map[{alias!r}] targets unknown field {target!r}")
    for template in query_policy.templates:
        for variable in template_variables(template):
            if variable in field_keys:
                continue
            if variable in query_policy.variable_map:
                continue
            raise ValueError(f"query template variable {variable!r} has no attribute mapping")


def _validate_source_policy(source_policy: SourcePolicy) -> None:
    groups = (
        source_policy.preferred_source_types,
        source_policy.context_source_types,
        source_policy.blocked_source_types,
    )
    for source_type in {item for group in groups for item in group}:
        if source_type not in KNOWN_SOURCE_TYPES:
            raise ValueError(f"unknown source type: {source_type}")

    preferred = set(source_policy.preferred_source_types)
    context = set(source_policy.context_source_types)
    blocked = set(source_policy.blocked_source_types)
    if preferred & blocked:
        raise ValueError("source_policy preferred and blocked source types overlap")
    if context & blocked:
        raise ValueError("source_policy context and blocked source types overlap")


def _validate_rating_policy(rating_policy: RatingPolicy) -> None:
    total_weight = sum(criterion.weight for criterion in rating_policy.criteria)
    if total_weight != 100:
        raise ValueError("rating_policy.criteria weights must sum to 100")
    for criterion in rating_policy.criteria:
        if criterion.evaluation in {RatingEvaluation.RULES, RatingEvaluation.HYBRID}:
            if criterion.rule_set is None:
                raise ValueError(f"criterion {criterion.key!r} needs rule_set")
            if criterion.rule_set not in KNOWN_RULE_SETS:
                raise ValueError(f"criterion {criterion.key!r} uses unknown rule_set")
        if criterion.evaluation in {RatingEvaluation.LLM, RatingEvaluation.HYBRID}:
            if criterion.llm_instruction is None:
                raise ValueError(f"criterion {criterion.key!r} needs llm_instruction")
        for evidence_type in criterion.evidence_types:
            if evidence_type not in KNOWN_EVIDENCE_TYPES:
                raise ValueError(
                    f"criterion {criterion.key!r} uses unknown evidence_type: {evidence_type}"
                )


def _validate_draft_policy(draft_policy: DraftPolicy) -> None:
    schema = DRAFT_OUTPUT_SCHEMAS[draft_policy.draft_type]
    unknown_sections = set(draft_policy.required_sections) - set(schema)
    if unknown_sections:
        raise ValueError(
            f"draft_policy.required_sections contains unknown sections: {sorted(unknown_sections)}"
        )
    if draft_policy.draft_type == "research_summary":
        required = {"summary", "key_findings", "evidence", "risks_or_uncertainties"}
        missing = required - set(draft_policy.required_sections)
        if missing:
            raise ValueError(f"research_summary is missing required sections: {sorted(missing)}")


def _validate_review_policy(review_policy: ReviewPolicy) -> None:
    for action in review_policy.actions:
        if action not in KNOWN_REVIEW_ACTIONS:
            raise ValueError(f"unknown review action: {action}")


def _ensure_non_empty(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _optional_non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    return _ensure_non_empty(value, "optional string")


def _ensure_identifier(value: str, field_name: str) -> str:
    cleaned = _ensure_non_empty(value, field_name)
    if re.fullmatch(r"[a-z][a-z0-9_]*", cleaned) is None:
        raise ValueError(f"{field_name} must be a lowercase identifier")
    return cleaned


def _optional_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    return _ensure_identifier(value, "optional identifier")


def _ensure_known(value: str, known_values: frozenset[str], field_name: str) -> str:
    cleaned = _ensure_non_empty(value, field_name)
    if cleaned not in known_values:
        raise ValueError(f"{field_name} must be one of: {', '.join(sorted(known_values))}")
    return cleaned


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _tuple_from(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _clean_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(item.strip() for item in value if item and item.strip())


APPLICATION_STUDENT_USE_CASE = UseCaseConfig(
    id="application_student",
    name="Bewerbung Student",
    description="Lokale Suche nach passenden Bewerbungszielen fuer studentische Profile.",
    version=1,
    attribute_schema=AttributeSchema(
        fields=(
            AttributeField("roles", "Rollen", AttributeFieldType.LIST, required=True),
            AttributeField("tech_keywords", "Technologien", AttributeFieldType.LIST),
            AttributeField("industry_keywords", "Branchen", AttributeFieldType.LIST),
            AttributeField("regions", "Regionen", AttributeFieldType.LIST),
            AttributeField("exclude_keywords", "Ausschlussbegriffe", AttributeFieldType.LIST),
        )
    ),
    query_policy=QueryPolicy(
        default_template_set="application_student",
        request_budget_default=25,
        results_per_query_default=5,
        variable_map={
            "role": "roles",
            "tech": "tech_keywords",
            "industry": "industry_keywords",
            "region": "regions",
        },
        templates=(
            "{role} {region} Karriere",
            "{role} {tech} {region}",
            "{role} {industry} {region}",
        ),
    ),
    source_policy=SourcePolicy(
        preferred_source_types=("company_site", "official_site"),
        blocked_source_types=("job_board", "social", "marketplace"),
        relevant_path_tokens=("career", "careers", "karriere", "jobs", "kontakt", "about"),
    ),
    rating_policy=RatingPolicy(
        llm_mode="light",
        min_score_for_review=50,
        min_score_for_draft=70,
        criteria=(
            RatingCriterion(
                key="role_fit",
                label="Rollenfit",
                weight=40,
                evaluation=RatingEvaluation.RULES,
                rule_set="role_keyword_match",
                evidence_types=("target_career", "target_page"),
                min_evidence_count=1,
            ),
            RatingCriterion(
                key="tech_fit",
                label="Tech-Fit",
                weight=30,
                evaluation=RatingEvaluation.RULES,
                rule_set="tech_keyword_match",
                evidence_types=("target_career", "target_about", "target_page"),
                min_evidence_count=1,
            ),
            RatingCriterion(
                key="region_fit",
                label="Regionaler Fit",
                weight=30,
                evaluation=RatingEvaluation.RULES,
                rule_set="region_keyword_match",
                evidence_types=(
                    "target_career",
                    "target_contact",
                    "target_about",
                    "target_homepage",
                    "target_page",
                ),
                min_evidence_count=1,
            ),
        ),
    ),
    draft_policy=DraftPolicy(
        draft_type="application_email",
        language="de",
        max_length_chars=3500,
    ),
    review_policy=ReviewPolicy(
        default_scope="use_case",
        actions=("approve", "reject", "blacklist"),
        columns=("domain", "source_type", "score", "recommended_action", "main_reason"),
    ),
)

COMPANY_OSINT_USE_CASE = UseCaseConfig(
    id="company_osint",
    name="Unternehmens-OSINT",
    description="Lokale Recherche zu Unternehmen, Quellenlage und belastbaren Hinweisen.",
    version=1,
    attribute_schema=AttributeSchema(
        fields=(
            AttributeField("topics", "Themen", AttributeFieldType.LIST, required=True),
            AttributeField("industries", "Branchen", AttributeFieldType.LIST),
            AttributeField("regions", "Regionen", AttributeFieldType.LIST),
            AttributeField("exclude_keywords", "Ausschlussbegriffe", AttributeFieldType.LIST),
        )
    ),
    query_policy=QueryPolicy(
        default_template_set="company_osint",
        request_budget_default=25,
        results_per_query_default=5,
        variable_map={
            "topic": "topics",
            "industry": "industries",
            "region": "regions",
        },
        templates=(
            "{topic} Unternehmen {region}",
            "{topic} Kontakt {region}",
            "{topic} Impressum {region}",
            "{topic} Services {region}",
            "{industry} Unternehmen {region}",
            "{industry} Dienstleister {region}",
            "{topic} Referenzen {region}",
        ),
        exclude_terms=(
            "jobs",
            "stellenangebote",
            "karriere",
            "praktikum",
            "werkstudent",
        ),
    ),
    source_policy=SourcePolicy(
        preferred_source_types=("company_site", "official_site"),
        context_source_types=("registry", "directory", "news"),
        blocked_source_types=("social",),
        relevant_path_tokens=("impressum", "about", "kontakt", "services", "products"),
    ),
    rating_policy=RatingPolicy(
        llm_mode="light",
        min_score_for_review=45,
        min_score_for_draft=65,
        criteria=(
            RatingCriterion(
                key="relevance",
                label="Relevanz",
                weight=40,
                evaluation=RatingEvaluation.LLM,
                evidence_types=(
                    "target_homepage",
                    "target_about",
                    "target_contact",
                    "target_page",
                    "context_directory",
                    "context_news",
                    "context_registry",
                    "context_source",
                ),
                min_evidence_count=1,
                llm_instruction="Bewerte, ob das Target fachlich zum OSINT-Thema passt.",
            ),
            RatingCriterion(
                key="credibility",
                label="Seriositaet",
                weight=30,
                evaluation=RatingEvaluation.HYBRID,
                rule_set="source_quality",
                evidence_types=(
                    "target_homepage",
                    "target_about",
                    "target_contact",
                    "context_directory",
                    "context_news",
                    "context_registry",
                    "context_source",
                ),
                llm_instruction="Bewerte, ob Quelle und Target serioes genug sind.",
            ),
            RatingCriterion(
                key="evidence_quality",
                label="Belegqualitaet",
                weight=30,
                evaluation=RatingEvaluation.HYBRID,
                rule_set="evidence_quality",
                evidence_types=(
                    "target_homepage",
                    "target_about",
                    "target_contact",
                    "target_page",
                    "context_directory",
                    "context_news",
                    "context_registry",
                    "context_source",
                ),
                min_evidence_count=1,
                llm_instruction="Bewerte, ob die gefundenen Belege konkret und belastbar sind.",
            ),
        ),
    ),
    draft_policy=DraftPolicy(
        draft_type="research_summary",
        language="de",
        max_length_chars=2500,
        required_sections=(
            "summary",
            "key_findings",
            "evidence",
            "risks_or_uncertainties",
        ),
    ),
    review_policy=ReviewPolicy(
        default_scope="use_case",
        actions=("approve", "reject", "blacklist"),
        columns=("domain", "source_type", "score", "recommended_action", "main_reason"),
    ),
)

DEFAULT_USE_CASES = (APPLICATION_STUDENT_USE_CASE, COMPANY_OSINT_USE_CASE)
DEFAULT_USE_CASE_BY_ID = {item.id: item for item in DEFAULT_USE_CASES}


__all__ = [
    "APPLICATION_STUDENT_USE_CASE",
    "COMPANY_OSINT_USE_CASE",
    "DEFAULT_USE_CASES",
    "DRAFT_OUTPUT_SCHEMAS",
    "AttributeField",
    "AttributeFieldType",
    "AttributeSchema",
    "DraftPolicy",
    "QueryPolicy",
    "RatingCriterion",
    "RatingEvaluation",
    "RatingPolicy",
    "ReviewPolicy",
    "SourcePolicy",
    "UseCaseConfig",
    "UseCaseStatus",
    "get_default_use_case",
    "template_variables",
    "validate_use_case_config",
]
