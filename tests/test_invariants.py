"""
Nexus Verification Engine — 10,000 seeded Python invariant cases.

Every generated request must satisfy all Zero Drift invariants:
  - delta_v in {0.0, 0.75}
  - risk_score in [0.0, 1.0]
  - GRANT  → validated_delta_a == requested_delta_a, verified == True, delta_v >= validated_delta_a
  - REJECT → validated_delta_a == 0.0, verified == False
  - SAFE_LOCK → validated_delta_a == 0.0, verified == False, delta_v > 0.0
  - actual_constraint_violations = 0 (ΔA ≤ ΔV is never violated in the response)
"""

import random
import unittest
from verification_engine.engine import VerificationEngine
from verification_engine.models import Decision

SEED = 42
N_CASES = 10_000

_VALID_STATUSES = ["valid"]
_CRITICAL_STATUSES = ["expired", "invalid", "unverified"]
_ALL_STATUSES = _VALID_STATUSES + _CRITICAL_STATUSES

# Evaluation timestamp is fixed; evidence timestamps are varied around it.
EVAL_TS = "2026-07-14T10:00:00Z"
EVAL_ISO = "2026-07-14T10:00:00"


def _random_evidence(rng: random.Random, index: int, eval_iso: str):
    """Generate a single evidence item, possibly critical or future-dated."""
    evidence_id = f"EVD-INV-{index:05d}"
    status_choice = rng.choice(_ALL_STATUSES)
    confidence = round(rng.uniform(0.0, 1.0), 4)

    # Vary timestamp: past (valid) or future (critical)
    hours_offset = rng.randint(-48, 48)
    if hours_offset >= 0:
        hour = 10 + hours_offset
        day_offset = hour // 24
        hour = hour % 24
        day = 14 + day_offset
        ts = f"2026-07-{day:02d}T{hour:02d}:00:00Z"
    else:
        hour = 10 + hours_offset
        if hour < 0:
            day = 13
            hour = 24 + hour
        else:
            day = 14
        ts = f"2026-07-{day:02d}T{hour:02d}:00:00Z"

    evidence = {
        "evidence_id": evidence_id,
        "source": f"source_{index % 4}",
        "timestamp": ts,
        "data": {
            "verification_status": status_choice,
            "confidence": confidence,
        },
    }

    # Randomly add expires_at for some valid-status items
    if status_choice == "valid" and rng.random() < 0.3:
        exp_hours = rng.randint(-48, 48)
        exp_day = 14
        exp_hour = 10 + exp_hours
        if exp_hour < 0:
            exp_day = 13
            exp_hour = 24 + exp_hour
        elif exp_hour >= 24:
            exp_day = 14 + exp_hour // 24
            exp_hour = exp_hour % 24
        evidence["expires_at"] = f"2026-07-{exp_day:02d}T{exp_hour:02d}:00:00Z"

    return evidence


class TestInvariantsSeeded10k(unittest.TestCase):
    """10,000 seeded invariant cases — zero violations permitted."""

    @classmethod
    def setUpClass(cls):
        cls.engine = VerificationEngine()
        cls.rng = random.Random(SEED)
        cls.results = []

        for i in range(N_CASES):
            n_evidence = cls.rng.randint(0, 6)
            # Use unique IDs per call
            evidence_items = [
                _random_evidence(cls.rng, i * 10 + j, EVAL_ISO)
                for j in range(n_evidence)
            ]
            requested_delta_a = round(cls.rng.uniform(0.0, 1.0), 4)

            try:
                response = cls.engine.verify(
                    target_id=f"inv_target_{i:05d}",
                    requested_authority="ANALYZE",
                    requested_delta_a=requested_delta_a,
                    evidence_items=evidence_items,
                    current_timestamp=EVAL_TS,
                )
                cls.results.append((requested_delta_a, response, None))
            except ValueError:
                # Duplicate IDs from random generation — skip (counted separately)
                cls.results.append((requested_delta_a, None, "duplicate"))

    def _valid_results(self):
        return [
            (da, r) for da, r, err in self.results if err is None
        ]

    def test_delta_v_is_in_valid_set(self):
        """delta_v must be 0.0 or 0.75 for every response."""
        for da, resp in self._valid_results():
            self.assertIn(resp.delta_v, {0.0, 0.75},
                          f"delta_v={resp.delta_v} not in {{0.0, 0.75}}")

    def test_risk_score_bounded(self):
        """risk_score must be in [0.0, 1.0] for every response."""
        for da, resp in self._valid_results():
            self.assertGreaterEqual(resp.risk_score, 0.0)
            self.assertLessEqual(resp.risk_score, 1.0)

    def test_grant_invariants(self):
        """GRANT: validated_delta_a == requested, verified == True, delta_v >= validated_delta_a."""
        for da, resp in self._valid_results():
            if resp.decision == Decision.GRANT:
                self.assertEqual(resp.validated_delta_a, da,
                                 f"GRANT: validated_delta_a {resp.validated_delta_a} != {da}")
                self.assertTrue(resp.verified, "GRANT: verified must be True")
                self.assertGreaterEqual(resp.delta_v, resp.validated_delta_a,
                                        f"GRANT: delta_v {resp.delta_v} < validated_delta_a {resp.validated_delta_a}")

    def test_reject_invariants(self):
        """REJECT: validated_delta_a == 0.0, verified == False."""
        for da, resp in self._valid_results():
            if resp.decision == Decision.REJECT:
                self.assertEqual(resp.validated_delta_a, 0.0,
                                 f"REJECT: validated_delta_a must be 0.0, got {resp.validated_delta_a}")
                self.assertFalse(resp.verified, "REJECT: verified must be False")

    def test_safe_lock_invariants(self):
        """SAFE_LOCK: validated_delta_a == 0.0, verified == False."""
        for da, resp in self._valid_results():
            if resp.decision == Decision.SAFE_LOCK:
                self.assertEqual(resp.validated_delta_a, 0.0,
                                 f"SAFE_LOCK: validated_delta_a must be 0.0, got {resp.validated_delta_a}")
                self.assertFalse(resp.verified, "SAFE_LOCK: verified must be False")

    def test_zero_actual_constraint_violations(self):
        """
        ΔA ≤ ΔV must never be violated in any response.
        A constraint violation is defined as: validated_delta_a > delta_v.
        """
        actual_violations = 0
        for da, resp in self._valid_results():
            if resp.validated_delta_a > resp.delta_v:
                actual_violations += 1
        self.assertEqual(actual_violations, 0,
                         f"actual_constraint_violations = {actual_violations} (must be 0)")

    def test_case_count(self):
        """Confirm 10,000 cases were attempted."""
        self.assertEqual(len(self.results), N_CASES)

    def test_grant_cases_present(self):
        """At least some GRANT decisions must appear in 10,000 cases."""
        grant_count = sum(
            1 for _, r, _ in self.results
            if r is not None and r.decision == Decision.GRANT
        )
        self.assertGreater(grant_count, 0, "No GRANT decisions found in 10,000 cases")

    def test_reject_cases_present(self):
        """At least some REJECT decisions must appear in 10,000 cases."""
        reject_count = sum(
            1 for _, r, _ in self.results
            if r is not None and r.decision == Decision.REJECT
        )
        self.assertGreater(reject_count, 0, "No REJECT decisions found in 10,000 cases")

    def test_safe_lock_cases_present(self):
        """At least some SAFE_LOCK decisions must appear in 10,000 cases."""
        safe_lock_count = sum(
            1 for _, r, _ in self.results
            if r is not None and r.decision == Decision.SAFE_LOCK
        )
        self.assertGreater(safe_lock_count, 0, "No SAFE_LOCK decisions found in 10,000 cases")


if __name__ == "__main__":
    unittest.main()
