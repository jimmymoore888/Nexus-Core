import json
import os
import tempfile
import unittest

from nexus_simulation import MONOPOLY_THRESHOLD
from napalm_test_suite import (
    NAPALM_WORLDS,
    SATDS_THREATS,
    NapalmWorldResult,
    SATDSThreatResult,
    generate_all_reports,
    run_napalm_worlds,
    run_satds,
)


FAST_SATDS_CYCLES = 100
FAST_NAPALM_CYCLES = 500
SEED = 7


class SATDSThreatDismantlingTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._results = run_satds(
            cycles_per_threat=FAST_SATDS_CYCLES, seed=SEED, report_dir=self._tmpdir
        )

    def test_layered_threat_simulation_runs(self):
        self.assertEqual(len(self._results), len(SATDS_THREATS))

    def test_every_threat_has_detected_layer(self):
        for r in self._results:
            self.assertIn(
                r.layer,
                ("Surface", "Signal", "Verification", "Influence", "Governance", "Core"),
                msg=f"{r.threat} has unexpected layer: {r.layer}",
            )

    def test_every_threat_has_containment_result(self):
        for r in self._results:
            self.assertIn(
                r.containment_result,
                ("contained", "breached"),
                msg=f"{r.threat} missing containment_result",
            )

    def test_every_threat_has_governors_activated(self):
        for r in self._results:
            self.assertIsInstance(r.governors_activated, list)
            self.assertGreater(
                len(r.governors_activated),
                0,
                msg=f"{r.threat} has empty governors list",
            )

    def test_actual_constraint_violations_zero(self):
        for r in self._results:
            self.assertEqual(
                r.actual_constraint_violations,
                0,
                msg=f"{r.threat}: actual_constraint_violations = {r.actual_constraint_violations}",
            )

    def test_verification_debt_final_zero(self):
        """SATDS threats use bounded signals ensuring ΔV covers ΔA demand."""
        total_debt = sum(r.verification_debt for r in self._results)
        self.assertAlmostEqual(
            total_debt,
            0.0,
            places=6,
            msg=f"total verification debt across SATDS threats: {total_debt}",
        )

    def test_da_leq_dv_holds_all_cycles(self):
        for r in self._results:
            for row in r.telemetry:
                self.assertLessEqual(
                    row["delta_a_granted"],
                    row["delta_v_budget"] + 1e-9,
                    msg=f"{r.threat} cycle {row['Cycle']}: ΔA > ΔV",
                )

    def test_weight_monopoly_never_achieved(self):
        for r in self._results:
            for row in r.telemetry:
                max_weight = max(row["Weight Distribution"].values())
                self.assertLess(
                    max_weight,
                    MONOPOLY_THRESHOLD,
                    msg=f"{r.threat} cycle {row['Cycle']}: weight monopoly {max_weight:.4f}",
                )


class NapalmWorldTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._results = run_napalm_worlds(
            cycles=FAST_NAPALM_CYCLES, seed=SEED, report_dir=self._tmpdir
        )

    def test_all_six_worlds_run(self):
        self.assertEqual(len(self._results), len(NAPALM_WORLDS))

    def test_every_world_has_metrics(self):
        for r in self._results:
            self.assertIsInstance(r.max_da_dv_ratio, float)
            self.assertIsInstance(r.mean_da_dv_ratio, float)
            self.assertIsInstance(r.final_verification_reserve, float)
            self.assertIsInstance(r.final_verification_debt, float)
            self.assertIsInstance(r.actual_constraint_violations, int)
            self.assertIsInstance(r.attempted_constraint_violations, int)

    def test_actual_constraint_violations_zero_all_worlds(self):
        for r in self._results:
            self.assertEqual(
                r.actual_constraint_violations,
                0,
                msg=f"{r.world}: actual_constraint_violations = {r.actual_constraint_violations}",
            )

    def test_granted_never_exceeds_budget_any_world(self):
        """delta_a_granted ≤ delta_v_budget holds even under napalm-level stress."""
        for r in self._results:
            for row in r.telemetry:
                self.assertLessEqual(
                    row["delta_a_granted"],
                    row["delta_v_budget"] + 1e-9,
                    msg=f"{r.world} cycle {row['Cycle']}: ΔA_granted > ΔV",
                )

    def test_all_worlds_pass(self):
        for r in self._results:
            self.assertTrue(r.passed, msg=f"{r.world} did not pass")

    def test_inflation_world_verification_debt_is_zero(self):
        inflation = next(r for r in self._results if r.world == "Napalm-Inflation")
        self.assertEqual(inflation.final_verification_debt, 0.0)


class ReportGenerationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._results = generate_all_reports(
            cycles_per_satds_threat=FAST_SATDS_CYCLES,
            napalm_cycles=FAST_NAPALM_CYCLES,
            seed=SEED,
            report_dir=self._tmpdir,
        )

    def test_all_report_files_created(self):
        expected = [
            "napalm_threat_dismantling_summary.json",
            "napalm_threat_dismantling_report.md",
            "napalm_layer_breakdown.csv",
            "napalm_summary.json",
            "napalm_report.md",
        ]
        for name in expected:
            self.assertTrue(
                os.path.isfile(os.path.join(self._tmpdir, name)),
                msg=f"Missing report file: {name}",
            )

    def test_satds_summary_json_content(self):
        path = os.path.join(self._tmpdir, "napalm_threat_dismantling_summary.json")
        with open(path) as fh:
            data = json.load(fh)
        self.assertEqual(data["actual_constraint_violations"], 0)
        self.assertIn("weakest_layer", data)
        self.assertIn("strongest_layer", data)
        self.assertIn("containment_success_rate", data)
        self.assertEqual(data["containment_success_rate"], 1.0)

    def test_napalm_summary_json_content(self):
        path = os.path.join(self._tmpdir, "napalm_summary.json")
        with open(path) as fh:
            data = json.load(fh)
        self.assertTrue(data["all_passed"])
        self.assertEqual(len(data["worlds"]), len(NAPALM_WORLDS))
        for w in data["worlds"]:
            self.assertEqual(w["actual_constraint_violations"], 0)

    def test_layer_breakdown_csv_has_all_rows(self):
        import csv as _csv

        path = os.path.join(self._tmpdir, "napalm_layer_breakdown.csv")
        with open(path, newline="") as fh:
            rows = list(_csv.DictReader(fh))
        self.assertEqual(len(rows), len(SATDS_THREATS))
        for row in rows:
            self.assertIn("threat", row)
            self.assertIn("layer", row)
            self.assertIn("governors_activated", row)
            self.assertIn("reached_core", row)


if __name__ == "__main__":
    unittest.main()
