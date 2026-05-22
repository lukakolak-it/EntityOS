from __future__ import annotations

import unittest

from target_radar.use_cases import (
    DEFAULT_USE_CASES,
    DRAFT_OUTPUT_SCHEMAS,
    SourcePolicy,
    UseCaseConfig,
    get_default_use_case,
    template_variables,
    validate_use_case_config,
)


class UseCaseSchemaTests(unittest.TestCase):
    def test_default_use_cases_are_valid_and_exportable(self) -> None:
        use_case_ids = {use_case.id for use_case in DEFAULT_USE_CASES}

        self.assertEqual(use_case_ids, {"application_student", "company_osint"})
        for use_case in DEFAULT_USE_CASES:
            exported = use_case.to_dict()
            roundtrip = UseCaseConfig.from_dict(exported)

            self.assertEqual(roundtrip.id, use_case.id)
            self.assertEqual(
                sum(item.weight for item in roundtrip.rating_policy.criteria),
                100,
            )

    def test_application_template_uses_explicit_variable_map(self) -> None:
        use_case = get_default_use_case("application_student")

        self.assertEqual(use_case.query_policy.variable_map["tech"], "tech_keywords")
        self.assertEqual(use_case.query_policy.variable_map["industry"], "industry_keywords")
        self.assertIn("{role} {tech} {region}", use_case.query_policy.templates)

    def test_template_variables_reject_unknown_mapping(self) -> None:
        payload = get_default_use_case("application_student").to_dict()
        payload["query_policy"]["templates"] = ["{unknown} {region} Karriere"]

        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_use_case_config(payload)

    def test_variable_map_must_target_existing_attribute_field(self) -> None:
        payload = get_default_use_case("application_student").to_dict()
        payload["query_policy"]["variable_map"]["role"] = "missing_roles"

        with self.assertRaisesRegex(ValueError, "missing_roles"):
            validate_use_case_config(payload)

    def test_source_policy_rejects_conflicting_source_types(self) -> None:
        payload = get_default_use_case("company_osint").to_dict()
        payload["source_policy"] = SourcePolicy(
            preferred_source_types=("company_site",),
            blocked_source_types=("company_site",),
        ).to_dict()

        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_use_case_config(payload)

    def test_rating_policy_requires_weights_to_sum_to_100(self) -> None:
        payload = get_default_use_case("application_student").to_dict()
        payload["rating_policy"]["criteria"][0]["weight"] = 39

        with self.assertRaisesRegex(ValueError, "sum to 100"):
            validate_use_case_config(payload)

    def test_rating_criteria_define_how_they_are_evaluated(self) -> None:
        payload = get_default_use_case("application_student").to_dict()
        payload["rating_policy"]["criteria"] = [
            {
                "key": "custom",
                "label": "Custom",
                "weight": 100,
                "evaluation": "rules",
            }
        ]

        with self.assertRaisesRegex(ValueError, "needs rule_set"):
            validate_use_case_config(payload)

        payload = get_default_use_case("application_student").to_dict()
        payload["rating_policy"]["criteria"] = [
            {
                "key": "custom",
                "label": "Custom",
                "weight": 100,
                "evaluation": "llm",
            }
        ]

        with self.assertRaisesRegex(ValueError, "needs llm_instruction"):
            validate_use_case_config(payload)

    def test_research_summary_has_output_schema_and_required_sections(self) -> None:
        use_case = get_default_use_case("company_osint")

        self.assertEqual(use_case.draft_policy.draft_type, "research_summary")
        self.assertIn("evidence", DRAFT_OUTPUT_SCHEMAS["research_summary"])
        self.assertIn("risks_or_uncertainties", use_case.draft_policy.required_sections)

    def test_template_variable_parser_rejects_format_specs(self) -> None:
        self.assertEqual(template_variables("{role} {region}"), frozenset({"role", "region"}))

        with self.assertRaisesRegex(ValueError, "format specs"):
            template_variables("{role!r}")


if __name__ == "__main__":
    unittest.main()
