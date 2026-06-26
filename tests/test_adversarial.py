import unittest

from adversarial_simulations import run_byzantine_scenario


class AdversarialSimulationTests(unittest.TestCase):
    def test_byzantine_4h0m_has_zero_violations(self):
        summary = run_byzantine_scenario(4, 0, cycles=5_000, seed=9)
        self.assertEqual(summary["actual_constraint_violations"], 0)

    def test_byzantine_1h3m_triggers_safe_lock(self):
        summary = run_byzantine_scenario(1, 3, cycles=5_000, seed=9)
        self.assertGreater(summary["cycles_in_safe_lock"], 0)

    def test_degraded_trust_reduces_da_dv_ratio(self):
        honest = run_byzantine_scenario(4, 0, cycles=5_000, seed=9)
        degraded = run_byzantine_scenario(2, 2, cycles=5_000, seed=9)
        self.assertLess(degraded["mean_da_dv_ratio"], honest["mean_da_dv_ratio"])

    def test_verification_debt_accumulates_under_attack(self):
        summary = run_byzantine_scenario(0, 4, cycles=5_000, seed=9)
        self.assertGreater(summary["final_verification_debt"], 0.0)


if __name__ == "__main__":
    unittest.main()
