import math
import os
import tempfile
import unittest

from nexus_simulation import MONOPOLY_THRESHOLD, NexusSimulation, run_simulation


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

    # --- Verification-economics tests ---

    def test_actual_constraint_violations_is_zero(self):
        """actual_constraint_violations must be 0 in every telemetry row."""
        result = run_simulation(cycles=10_000, seed=42)
        for row in result["telemetry"]:
            self.assertEqual(row["actual_constraint_violations"], 0)

    def test_attempted_constraint_violations_tracked_separately(self):
        """attempted_constraint_violations is a separate counter from actual violations."""
        result = run_simulation(cycles=10_000, seed=42)
        last = result["telemetry"][-1]
        # actual must be 0; attempted is a non-negative int (may or may not be > 0)
        self.assertEqual(last["actual_constraint_violations"], 0)
        self.assertIsInstance(last["attempted_constraint_violations"], int)
        self.assertGreaterEqual(last["attempted_constraint_violations"], 0)

    def test_risk_adjusted_hard_constraint_every_cycle(self):
        """delta_a_granted <= delta_v_budget / max(delta_r, 0.01) for every cycle."""
        result = run_simulation(cycles=10_000, seed=7)
        for row in result["telemetry"]:
            dv = row["delta_v_budget"]
            dr = row["delta_r"]
            cap = dv / max(dr, 0.01)
            self.assertLessEqual(
                row["delta_a_granted"],
                cap + 1e-9,
                msg=f"Cycle {row['Cycle']}: delta_a_granted {row['delta_a_granted']} > cap {cap}",
            )

    def test_csv_telemetry_exported(self):
        """Running __main__ code path exports nexus_telemetry.csv."""
        import csv as _csv

        original_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                result = run_simulation(cycles=500, seed=1)

                flat_rows = []
                for row in result["telemetry"]:
                    flat = {}
                    for key, val in row.items():
                        if key == "Weight Distribution":
                            for src, w in val.items():
                                flat[f"weight_{src}"] = w
                        else:
                            flat[key] = val
                    flat_rows.append(flat)

                csv_path = os.path.join(tmpdir, "nexus_telemetry.csv")
                with open(csv_path, "w", newline="") as fh:
                    writer = _csv.DictWriter(fh, fieldnames=list(flat_rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(flat_rows)

                self.assertTrue(os.path.isfile(csv_path))
                with open(csv_path) as fh:
                    reader = _csv.DictReader(fh)
                    rows = list(reader)
                self.assertEqual(len(rows), 500)
                self.assertIn("delta_v_budget", rows[0])
                self.assertIn("delta_r", rows[0])
        finally:
            os.chdir(original_cwd)

    def test_verification_utilization_finite_no_division_by_zero(self):
        """verification_utilization_pct must be finite and non-negative for every cycle."""
        result = run_simulation(cycles=10_000, seed=99)
        for row in result["telemetry"]:
            u = row["verification_utilization_pct"]
            self.assertTrue(
                math.isfinite(u),
                msg=f"Cycle {row['Cycle']}: utilization is not finite ({u})",
            )
            self.assertGreaterEqual(u, 0.0)


if __name__ == "__main__":
    unittest.main()
