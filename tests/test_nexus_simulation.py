import math
import os
import subprocess
import sys
import tempfile
import unittest

from nexus_simulation import (
    CONSTRAINT_TOLERANCE,
    MONOPOLY_THRESHOLD,
    NexusCore,
    NexusSimulation,
    _risk_adjusted_capacity,
    export_telemetry_csv,
    run_simulation,
)


class NexusSimulationTests(unittest.TestCase):
    def test_constraint_enforced_over_long_run(self):
        result = run_simulation(cycles=100_000, seed=17)
        self.assertEqual(result["summary"]["constraint_violations"], 0)
        self.assertTrue(result["success"]["zero_constraint_violations"])
        self.assertTrue(result["success"]["stable_100k_cycles"])

    def test_weight_distribution_is_normalized_and_non_monopolistic(self):
        result = run_simulation(cycles=20_000, seed=4)
        weights = result["telemetry"][-1]["Weight Distribution"]
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)
        self.assertLess(max(weights.values()), MONOPOLY_THRESHOLD)

    def test_deceptive_and_hostile_worlds_trigger_safety_features(self):
        sim = NexusSimulation(seed=23)
        result = sim.run(cycles=40_000)
        self.assertGreater(result["summary"]["corrupted_detections"], 0)
        self.assertGreater(result["summary"]["safe_lock_events"], 0)
        self.assertGreater(result["summary"]["recovery_events"], 0)

    def test_boring_world_rejects_noise(self):
        result = run_simulation(cycles=100_000, seed=33)
        self.assertLess(result["summary"]["avg_boring_adaptation"], 0.01)
        self.assertTrue(result["success"]["boring_noise_rejected"])

    def test_attempted_constraint_violations_may_exceed_zero(self):
        core = NexusCore()
        core.adaptation_state = 3.0
        row = core.step(
            {
                "world": "honest",
                "signals": {
                    "sensor": 0.02,
                    "log": 0.02,
                    "consensus": 0.02,
                    "external": 0.02,
                },
                "environment_shift": 0.0,
                "hostile_spike": False,
            },
            cycle=1,
        )
        self.assertEqual(row["attempted_constraint_violations"], 1)
        self.assertEqual(row["actual_constraint_violations"], 0)
        self.assertGreater(core.verification_debt, 0.0)

    def test_actual_constraint_violations_remain_zero(self):
        result = run_simulation(cycles=100_000, seed=7)
        self.assertEqual(result["summary"]["actual_constraint_violations"], 0)
        self.assertTrue(result["success"]["zero_constraint_violations"])
        self.assertEqual(
            sum(row["actual_constraint_violations"] for row in result["telemetry"]),
            0,
        )

    def test_constraint_violations_alias_matches_actual(self):
        # constraint_violations is an alias for actual_constraint_violations.
        result = run_simulation(cycles=20_000, seed=4)
        self.assertEqual(
            result["summary"]["constraint_violations"],
            result["summary"]["actual_constraint_violations"],
        )

    def test_telemetry_row_contains_new_columns(self):
        result = run_simulation(cycles=1_000, seed=7)
        row = result["telemetry"][-1]
        self.assertIn("delta_v_budget", row)
        self.assertIn("delta_a_demand", row)
        self.assertIn("delta_a_granted", row)
        self.assertIn("delta_r", row)
        self.assertIn("verification_utilization_pct", row)
        self.assertIn("verification_reserve", row)
        self.assertIn("verification_debt", row)
        self.assertIn("governance_interventions", row)
        self.assertIn("attempted_constraint_violations", row)
        self.assertIn("actual_constraint_violations", row)
        self.assertIn("Attempted Constraint Violations", row)
        self.assertIn("Actual Constraint Violations", row)
        self.assertIn("Constraint Violations", row)
        self.assertIsInstance(row["Attempted Constraint Violations"], int)
        self.assertIsInstance(row["Actual Constraint Violations"], int)
        self.assertIsInstance(row["Constraint Violations"], int)
        self.assertEqual(
            row["Constraint Violations"],
            row["Actual Constraint Violations"],
        )

    def test_risk_adjusted_constraint_holds_for_every_cycle(self):
        result = run_simulation(cycles=25_000, seed=9)
        for row in result["telemetry"]:
            hard_limit = _risk_adjusted_capacity(row["delta_v_budget"], row["delta_r"])
            self.assertLessEqual(
                row["delta_a_granted"],
                hard_limit + CONSTRAINT_TOLERANCE,
            )

    def test_verification_utilization_is_finite(self):
        result = run_simulation(cycles=25_000, seed=12)
        for row in result["telemetry"]:
            utilization = row["verification_utilization_pct"]
            self.assertTrue(math.isfinite(utilization))
            self.assertGreaterEqual(utilization, 0.0)

    def test_summary_contains_verification_economics_metrics(self):
        result = run_simulation(cycles=5_000, seed=7)
        summary = result["summary"]
        self.assertIn("Total_VEarned", summary)
        self.assertIn("Total_VSpent", summary)
        self.assertIn("VReserve_Final", summary)
        self.assertIn("VDebt_Final", summary)
        self.assertIn("Mean_Utilization", summary)
        self.assertIn("Max_Utilization", summary)
        self.assertIn("Governance_Intervention_Rate", summary)
        self.assertIn("VInflation_Detected", summary)
        self.assertIn("Recursion_Events", summary)
        self.assertIn("Mean_DA_DV_Ratio", summary)
        self.assertGreaterEqual(summary["Total_VEarned"], summary["Total_VSpent"])

    def test_csv_export_generates_valid_file(self):
        result = run_simulation(cycles=500, seed=7)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "telemetry.csv")
            export_telemetry_csv(result["telemetry"], path=csv_path)
            self.assertTrue(os.path.exists(csv_path))
            with open(csv_path, encoding="utf-8") as f:
                lines = f.readlines()
            # Header + one row per cycle
            self.assertEqual(len(lines), 501)
            header = lines[0].strip()
            self.assertIn("delta_v_budget", header)
            self.assertIn("verification_utilization_pct", header)
            self.assertIn("Attempted Constraint Violations", header)
            self.assertIn("Actual Constraint Violations", header)
            self.assertIn("Constraint Violations", header)

    def test_running_module_directly_generates_csv(self):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "nexus_simulation.py")
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [sys.executable, script_path],
                cwd=tmpdir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "nexus_telemetry.csv")))


if __name__ == "__main__":
    unittest.main()
