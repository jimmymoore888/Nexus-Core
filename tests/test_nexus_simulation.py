import os
import tempfile
import unittest

from nexus_simulation import (
    MONOPOLY_THRESHOLD,
    NexusSimulation,
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
        # seed=7 over 100k cycles is known to produce at least one attempted violation
        # (raw unclamped transform demand exceeds verification capacity).
        result = run_simulation(cycles=100_000, seed=7)
        self.assertGreater(result["summary"]["attempted_constraint_violations"], 0)

    def test_actual_constraint_violations_remain_zero(self):
        # The ΔA ≤ ΔV invariant must hold: applied adaptation never exceeds the
        # verification bound after clamping enforcement.
        result = run_simulation(cycles=100_000, seed=7)
        self.assertEqual(result["summary"]["actual_constraint_violations"], 0)
        self.assertTrue(result["success"]["zero_constraint_violations"])

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
        self.assertIn("Attempted Constraint Violations", row)
        self.assertIn("Actual Constraint Violations", row)
        self.assertIn("Constraint Violations", row)
        self.assertIsInstance(row["Attempted Constraint Violations"], int)
        self.assertIsInstance(row["Actual Constraint Violations"], int)

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
            self.assertIn("Attempted Constraint Violations", header)
            self.assertIn("Actual Constraint Violations", header)
            self.assertIn("Constraint Violations", header)


if __name__ == "__main__":
    unittest.main()
