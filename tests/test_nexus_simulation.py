import unittest

from nexus_simulation import NexusSimulation, run_simulation


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
        self.assertLess(max(weights.values()), 0.60)

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


if __name__ == "__main__":
    unittest.main()
