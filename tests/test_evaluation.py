from __future__ import annotations

import unittest

from target_radar.evaluation import DEFAULT_EVALUATION_FIXTURE, run_evaluation


class EvaluationTests(unittest.TestCase):
    def test_engine_eval_baseline_passes(self) -> None:
        result = run_evaluation(DEFAULT_EVALUATION_FIXTURE)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["total"], 24)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["sections"]["source_quality"]["total"], 12)
        self.assertEqual(result["sections"]["rating"]["total"], 8)
        self.assertEqual(result["sections"]["draft"]["total"], 4)


if __name__ == "__main__":
    unittest.main()
