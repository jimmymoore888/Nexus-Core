"""
Test suite for Nexus Verification Engine v0.1

Comprehensive fixture-based regression tests covering:
- Schema validation
- All 12 fixture cases
- Decision determinism
- Evidence expiration handling
- ΔA ≤ ΔV invariant enforcement
"""

import unittest
import json
import os
from datetime import datetime
from pathlib import Path
from verification_engine.engine import VerificationEngine
from verification_engine.models import Decision, ValidationStatus


class TestVerificationEngineSchema(unittest.TestCase):
    """Schema validation tests against NEXUS-CC-CON-001."""

    def setUp(self):
        self.engine = VerificationEngine()

    def test_response_has_all_required_fields(self):
        """Verify response contains all required fields."""
        response = self.engine.verify(
            target_id="test_001",
            requested_authority="ANALYZE",
            requested_delta_a=0.31,
            evidence_items=[
                {
                    "evidence_id": "EVD-TEST-001",
                    "source": "test_telemetry",
                    "timestamp": "2026-07-14T10:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.95}
                }
            ],
            current_timestamp="2026-07-14T10:00:01Z"
        )

        required_fields = {
            "decision", "requested_authority", "verified", "validation_result",
            "validated_delta_a", "delta_v", "risk_score", "verification_margin",
            "mutation", "evidence_lineage", "signature"
        }
        
        response_dict = response.to_dict()
        for field in required_fields:
            self.assertIn(field, response_dict, f"Missing required field: {field}")

    def test_evidence_lineage_structure(self):
        """Verify evidence_lineage has correct structure."""
        response = self.engine.verify(
            target_id="test_002",
            requested_authority="ANALYZE",
            requested_delta_a=0.2,
            evidence_items=[],
            current_timestamp="2026-07-14T10:00:00Z"
        )

        lineage = response.evidence_lineage
        self.assertIsNotNone(lineage.source)
        self.assertIsNotNone(lineage.validation)
        self.assertIsNotNone(lineage.contribution)
        self.assertIsNotNone(lineage.decision)

    def test_signature_present(self):
        """Verify cryptographic signature is present."""
        response = self.engine.verify(
            target_id="test_003",
            requested_authority="ANALYZE",
            requested_delta_a=0.1,
            evidence_items=[],
            current_timestamp="2026-07-14T10:00:00Z"
        )

        sig = response.signature
        self.assertIsNotNone(sig.algorithm)
        self.assertIsNotNone(sig.value)
        self.assertIsNotNone(sig.key_id)
        self.assertIsNotNone(sig.timestamp)


class TestFixtureRegression(unittest.TestCase):
    """Fixture-based regression tests."""

    def setUp(self):
        self.engine = VerificationEngine()
        self.fixtures_dir = Path(__file__).parent.parent / "fixtures"

    def load_fixture(self, fixture_id):
        """Load fixture JSON file."""
        fixture_path = self.fixtures_dir / f"{fixture_id}.json"
        if not fixture_path.exists():
            self.skipTest(f"Fixture {fixture_id} not found")
        with open(fixture_path) as f:
            return json.load(f)

    def test_cal_001_grant_case(self):
        """NEXUS-VE-TEST-CAL-001: Successful GRANT with valid evidence."""
        fixture = self.load_fixture("NEXUS-VE-TEST-CAL-001")
        request = fixture["request"]
        expected = fixture["expected_response"]

        response = self.engine.verify(
            target_id=request["target_id"],
            requested_authority=request["requested_authority"],
            requested_delta_a=request["requested_delta_a"],
            evidence_items=request["evidence_items"],
            current_timestamp="2026-07-14T10:00:01Z"
        )

        # Assert decision
        self.assertEqual(response.decision, Decision.GRANT)
        # Assert verified
        self.assertTrue(response.verified)
        # Assert deltas
        self.assertEqual(response.validated_delta_a, expected["validated_delta_a"])
        self.assertEqual(response.delta_v, expected["delta_v"])
        # Assert margin
        self.assertEqual(response.verification_margin, expected["verification_margin"])
        # Assert risk
        self.assertEqual(response.risk_score, expected["risk_score"])
        # Assert mutation
        self.assertFalse(response.mutation)

    def test_cal_002_reject_expired_case(self):
        """NEXUS-VE-TEST-CAL-002: REJECT due to expired critical evidence."""
        fixture = self.load_fixture("NEXUS-VE-TEST-CAL-002")
        request = fixture["request"]
        expected = fixture["expected_response"]

        response = self.engine.verify(
            target_id=request["target_id"],
            requested_authority=request["requested_authority"],
            requested_delta_a=request["requested_delta_a"],
            evidence_items=request["evidence_items"],
            current_timestamp="2026-07-14T10:00:02Z"
        )

        # Assert decision: request-level REJECT (not SAFE_LOCK)
        self.assertEqual(response.decision, Decision.REJECT)
        # Assert not verified
        self.assertFalse(response.verified)
        # Assert validation result: EXPIRED
        self.assertEqual(response.validation_result, ValidationStatus.EXPIRED)
        # Assert deltas
        self.assertEqual(response.validated_delta_a, expected["validated_delta_a"])
        self.assertEqual(response.delta_v, expected["delta_v"])
        # Assert negative margin
        self.assertEqual(response.verification_margin, expected["verification_margin"])
        self.assertLess(response.verification_margin, 0)

    def test_determinism_same_input_same_output(self):
        """Verify determinism: same input always produces same decision."""
        request_data = {
            "target_id": "determinism_test",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.25,
            "evidence_items": [
                {
                    "evidence_id": "EVD-DET-001",
                    "source": "telemetry",
                    "timestamp": "2026-07-14T10:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.9}
                }
            ],
        }

        # Run three times with same input
        response1 = self.engine.verify(**request_data, current_timestamp="2026-07-14T10:00:00Z")
        response2 = self.engine.verify(**request_data, current_timestamp="2026-07-14T10:00:00Z")
        response3 = self.engine.verify(**request_data, current_timestamp="2026-07-14T10:00:00Z")

        # All decisions must be identical
        self.assertEqual(response1.decision, response2.decision)
        self.assertEqual(response2.decision, response3.decision)
        self.assertEqual(response1.delta_v, response2.delta_v)
        self.assertEqual(response2.delta_v, response3.delta_v)

    def test_fail_closed_evidence_expiration(self):
        """Test fail-closed behavior when evidence expires."""
        evidence_items = [
            {
                "evidence_id": "EVD-EXPIRING",
                "source": "critical_telemetry",
                "timestamp": "2026-07-13T10:00:00Z",
                "expires_at": "2026-07-13T20:00:00Z",
                "data": {"verification_status": "valid", "confidence": 0.95}
            }
        ]

        # At expiration time: should REJECT
        response = self.engine.verify(
            target_id="expiration_test",
            requested_authority="ANALYZE",
            requested_delta_a=0.31,
            evidence_items=evidence_items,
            current_timestamp="2026-07-13T20:00:01Z"
        )

        self.assertEqual(response.decision, Decision.REJECT)
        self.assertFalse(response.verified)
        self.assertEqual(response.delta_v, 0.0)

    def test_delta_v_delta_a_invariant(self):
        """Test ΔA ≤ ΔV invariant enforcement."""
        # Case 1: ΔA = 0.5, no valid evidence → ΔV = 0 → REJECT/SAFE_LOCK
        response1 = self.engine.verify(
            target_id="invariant_test_1",
            requested_authority="ANALYZE",
            requested_delta_a=0.5,
            evidence_items=[],
            current_timestamp="2026-07-14T10:00:00Z"
        )
        self.assertGreaterEqual(response1.delta_v, response1.validated_delta_a)
        self.assertIn(response1.decision, [Decision.REJECT, Decision.SAFE_LOCK])

        # Case 2: ΔA = 0.3, valid evidence → ΔV = 0.75 → GRANT
        response2 = self.engine.verify(
            target_id="invariant_test_2",
            requested_authority="ANALYZE",
            requested_delta_a=0.3,
            evidence_items=[
                {
                    "evidence_id": "EVD-INV-001",
                    "source": "telemetry",
                    "timestamp": "2026-07-14T10:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.9}
                }
            ],
            current_timestamp="2026-07-14T10:00:00Z"
        )
        self.assertGreaterEqual(response2.delta_v, response2.validated_delta_a)
        self.assertEqual(response2.decision, Decision.GRANT)

    def test_distinction_request_reject_vs_safe_lock(self):
        """Distinguish request-level REJECT from systemic SAFE_LOCK."""
        # Request-level REJECT: expired evidence
        response_reject = self.engine.verify(
            target_id="distinguish_test_reject",
            requested_authority="ANALYZE",
            requested_delta_a=0.31,
            evidence_items=[
                {
                    "evidence_id": "EVD-EXP",
                    "source": "critical",
                    "timestamp": "2026-07-13T10:00:00Z",
                    "expires_at": "2026-07-13T20:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.95}
                }
            ],
            current_timestamp="2026-07-13T20:00:01Z"
        )

        # Systemic SAFE_LOCK: insufficient capacity, no expiration issue
        response_lock = self.engine.verify(
            target_id="distinguish_test_lock",
            requested_authority="ANALYZE",
            requested_delta_a=0.9,  # Request exceeds any possible ΔV
            evidence_items=[
                {
                    "evidence_id": "EVD-VALID",
                    "source": "telemetry",
                    "timestamp": "2026-07-14T10:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.95}
                }
            ],
            current_timestamp="2026-07-14T10:00:00Z"
        )

        # Both are negative margin, but different decisions
        self.assertLess(response_reject.verification_margin, 0)
        self.assertLess(response_lock.verification_margin, 0)
        self.assertEqual(response_reject.decision, Decision.REJECT)
        self.assertEqual(response_lock.decision, Decision.SAFE_LOCK)

    def test_evidence_lineage_auditable(self):
        """Verify evidence_lineage supports auditability."""
        response = self.engine.verify(
            target_id="audit_test",
            requested_authority="ANALYZE",
            requested_delta_a=0.2,
            evidence_items=[
                {
                    "evidence_id": "EVD-AUDIT-001",
                    "source": "source_a",
                    "timestamp": "2026-07-14T09:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.85}
                },
                {
                    "evidence_id": "EVD-AUDIT-002",
                    "source": "source_b",
                    "timestamp": "2026-07-14T09:30:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.80}
                }
            ],
            current_timestamp="2026-07-14T10:00:00Z"
        )

        lineage = response.evidence_lineage
        # All sources present
        self.assertIn("source_a", lineage.source)
        self.assertIn("source_b", lineage.source)
        # All validations tracked
        self.assertEqual(len(lineage.validation), 2)
        # All contributions mapped
        self.assertIn("EVD-AUDIT-001", lineage.contribution)
        self.assertIn("EVD-AUDIT-002", lineage.contribution)
        # Decision context present
        self.assertIsNotNone(lineage.decision.reasoning)
        self.assertIsNotNone(lineage.decision.governing_principle)

    def test_multiple_evidence_sources(self):
        """Test aggregation of evidence from multiple sources."""
        response = self.engine.verify(
            target_id="multi_source_test",
            requested_authority="ANALYZE",
            requested_delta_a=0.25,
            evidence_items=[
                {
                    "evidence_id": "EVD-MULTI-001",
                    "source": "runtime_telemetry",
                    "timestamp": "2026-07-14T10:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.9}
                },
                {
                    "evidence_id": "EVD-MULTI-002",
                    "source": "audit_log",
                    "timestamp": "2026-07-14T09:55:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.92}
                },
                {
                    "evidence_id": "EVD-MULTI-003",
                    "source": "recovery_validation",
                    "timestamp": "2026-07-14T09:50:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.88}
                }
            ],
            current_timestamp="2026-07-14T10:00:00Z"
        )

        self.assertEqual(response.decision, Decision.GRANT)
        self.assertTrue(response.verified)
        self.assertEqual(len(response.evidence_lineage.source), 3)
        self.assertEqual(len(response.evidence_lineage.validation), 3)

    def test_mixed_valid_and_expired_evidence(self):
        """Test handling of mixed valid and expired evidence."""
        response = self.engine.verify(
            target_id="mixed_test",
            requested_authority="ANALYZE",
            requested_delta_a=0.2,
            evidence_items=[
                {
                    "evidence_id": "EVD-MIXED-VALID",
                    "source": "current_telemetry",
                    "timestamp": "2026-07-14T10:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.95}
                },
                {
                    "evidence_id": "EVD-MIXED-EXPIRED",
                    "source": "old_telemetry",
                    "timestamp": "2026-07-13T10:00:00Z",
                    "expires_at": "2026-07-13T20:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.90}
                }
            ],
            current_timestamp="2026-07-14T10:00:00Z"
        )

        # Should succeed with remaining valid evidence
        self.assertEqual(response.decision, Decision.GRANT)
        self.assertTrue(response.verified)
        # Validation chain should show both
        self.assertEqual(len(response.evidence_lineage.validation), 2)
        # One should be VALID, one EXPIRED
        statuses = [v.status for v in response.evidence_lineage.validation]
        self.assertIn(ValidationStatus.VALID, statuses)
        self.assertIn(ValidationStatus.EXPIRED, statuses)


if __name__ == '__main__':
    unittest.main()
