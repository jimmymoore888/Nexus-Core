import json
import subprocess
import unittest
from pathlib import Path

from verification_engine.engine import VerificationEngine


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_node_verify(request_payload, current_timestamp):
    payload = dict(request_payload)
    payload["current_timestamp"] = current_timestamp
    proc = subprocess.run(
        ["node", "tests/node_verify_wrapper.js"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=True,
    )
    return json.loads(proc.stdout)


class TestCrossProcessDeterminism(unittest.TestCase):
    def setUp(self):
        self.engine = VerificationEngine()
        self.fixtures_dir = REPO_ROOT / "fixtures"

    def _load_fixture_request(self, fixture_id):
        with (self.fixtures_dir / f"{fixture_id}.json").open() as f:
            return json.load(f)["request"]

    def _assert_python_node_match(self, request_payload, current_timestamp):
        py_response = self.engine.verify(
            target_id=request_payload["target_id"],
            requested_authority=request_payload["requested_authority"],
            requested_delta_a=request_payload["requested_delta_a"],
            evidence_items=request_payload["evidence_items"],
            current_timestamp=current_timestamp,
        ).to_dict()
        node_result = _run_node_verify(request_payload, current_timestamp)
        self.assertTrue(node_result["ok"], node_result.get("error"))
        node_response = node_result["response"]

        self.assertEqual(py_response["decision"], node_response["decision"])
        self.assertEqual(py_response["validated_delta_a"], node_response["validated_delta_a"])
        self.assertEqual(py_response["delta_v"], node_response["delta_v"])
        self.assertEqual(py_response["evidence_lineage"]["decision"]["timestamp"], node_response["evidence_lineage"]["decision"]["timestamp"])
        self.assertEqual(py_response["signature"]["timestamp"], node_response["signature"]["timestamp"])
        self.assertEqual(py_response["signature"]["algorithm"], node_response["signature"]["algorithm"])
        self.assertEqual(py_response["signature"]["value"], node_response["signature"]["value"])
        self.assertEqual(py_response["evidence_lineage"]["validation"], node_response["evidence_lineage"]["validation"])

    def test_cal_001_python_node_equality(self):
        request_payload = self._load_fixture_request("NEXUS-VE-TEST-CAL-001")
        self._assert_python_node_match(request_payload, "2026-07-14T10:00:01Z")

    def test_cal_002_python_node_equality(self):
        request_payload = self._load_fixture_request("NEXUS-VE-TEST-CAL-002")
        self._assert_python_node_match(request_payload, "2026-07-14T10:00:02Z")

    def test_duplicate_evidence_ids_match_error(self):
        request_payload = {
            "target_id": "dup_cross_process",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": [
                {
                    "evidence_id": "DUP-ID",
                    "source": "a",
                    "timestamp": "2026-07-14T09:00:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.9},
                },
                {
                    "evidence_id": "DUP-ID",
                    "source": "b",
                    "timestamp": "2026-07-14T09:30:00Z",
                    "data": {"verification_status": "valid", "confidence": 0.8},
                },
            ],
        }

        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14T10:00:00Z",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertFalse(node_result["ok"])
        self.assertIn("Duplicate evidence_id", str(py_err.exception))
        self.assertIn("Duplicate evidence_id", node_result["error"])

    def test_unknown_verification_status_fails_closed_with_parity(self):
        request_payload = {
            "target_id": "status_unknown",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": [
                {
                    "evidence_id": "E1",
                    "source": "telemetry",
                    "timestamp": "2026-07-14T09:00:00Z",
                    "data": {"verification_status": "mystery", "confidence": 0.9},
                }
            ],
        }
        py_response = self.engine.verify(
            target_id=request_payload["target_id"],
            requested_authority=request_payload["requested_authority"],
            requested_delta_a=request_payload["requested_delta_a"],
            evidence_items=request_payload["evidence_items"],
            current_timestamp="2026-07-14T10:00:00Z",
        ).to_dict()
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertTrue(node_result["ok"], node_result.get("error"))
        node_response = node_result["response"]
        self.assertEqual(py_response["decision"], "REJECT")
        self.assertEqual(py_response["delta_v"], 0.0)
        self.assertEqual(py_response["validated_delta_a"], 0.0)
        self.assertEqual(py_response["evidence_lineage"]["validation"][0]["status"], "UNVERIFIED")
        self.assertEqual(py_response["validation_result"], "INVALID")
        self.assertEqual(py_response["decision"], node_response["decision"])
        self.assertEqual(py_response["validation_result"], node_response["validation_result"])
        self.assertEqual(
            py_response["evidence_lineage"]["validation"],
            node_response["evidence_lineage"]["validation"],
        )

    def test_missing_verification_status_fails_closed_with_parity(self):
        request_payload = {
            "target_id": "status_missing",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": [
                {
                    "evidence_id": "E1",
                    "source": "telemetry",
                    "timestamp": "2026-07-14T09:00:00Z",
                    "data": {"confidence": 0.9},
                }
            ],
        }
        self._assert_python_node_match(request_payload, "2026-07-14T10:00:00Z")
        py_response = self.engine.verify(
            target_id=request_payload["target_id"],
            requested_authority=request_payload["requested_authority"],
            requested_delta_a=request_payload["requested_delta_a"],
            evidence_items=request_payload["evidence_items"],
            current_timestamp="2026-07-14T10:00:00Z",
        ).to_dict()
        self.assertEqual(py_response["decision"], "REJECT")
        self.assertEqual(py_response["delta_v"], 0.0)
        self.assertEqual(py_response["validated_delta_a"], 0.0)

    def test_invalid_requested_delta_a_match_error(self):
        request_payload = {
            "target_id": "bad_delta",
            "requested_authority": "ANALYZE",
            "requested_delta_a": "0.2",
            "evidence_items": [],
        }

        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14T10:00:00Z",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertFalse(node_result["ok"])
        self.assertIn("requested_delta_a must be", str(py_err.exception))
        self.assertIn("requested_delta_a must be", node_result["error"])

    def test_invalid_current_timestamp_match_error(self):
        request_payload = {
            "target_id": "bad_ts",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": [],
        }

        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14 10:00:00",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14 10:00:00")
        self.assertFalse(node_result["ok"])
        self.assertIn("current_timestamp must be", str(py_err.exception))
        self.assertIn("current_timestamp must be", node_result["error"])

    def test_confidence_string_bad_matches_error(self):
        request_payload = {
            "target_id": "bad_confidence",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": [
                {
                    "evidence_id": "E1",
                    "source": "telemetry",
                    "timestamp": "2026-07-14T09:00:00Z",
                    "data": {"verification_status": "valid", "confidence": "bad"},
                }
            ],
        }

        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14T10:00:00Z",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertFalse(node_result["ok"])
        self.assertIn("confidence must be a finite numeric value", str(py_err.exception))
        self.assertIn("confidence must be a finite numeric value", node_result["error"])

    def test_non_object_data_matches_error(self):
        request_payload = {
            "target_id": "bad_data_object",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": [
                {
                    "evidence_id": "E1",
                    "source": "telemetry",
                    "timestamp": "2026-07-14T09:00:00Z",
                    "data": "bad",
                }
            ],
        }
        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14T10:00:00Z",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertFalse(node_result["ok"])
        self.assertIn("data must be an object", str(py_err.exception))
        self.assertIn("data must be an object", node_result["error"])

    def test_non_list_evidence_items_matches_error(self):
        request_payload = {
            "target_id": "bad_evidence_items",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": {},
        }
        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14T10:00:00Z",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertFalse(node_result["ok"])
        self.assertIn("evidence_items must be", str(py_err.exception))
        self.assertIn("evidence_items must be", node_result["error"])

    def test_non_string_requested_authority_matches_error(self):
        request_payload = {
            "target_id": "bad_requested_authority",
            "requested_authority": None,
            "requested_delta_a": 0.2,
            "evidence_items": [],
        }
        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14T10:00:00Z",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertFalse(node_result["ok"])
        self.assertIn("requested_authority must be a non-empty string", str(py_err.exception))
        self.assertIn("requested_authority must be a non-empty string", node_result["error"])

    def test_malformed_timestamp_with_unknown_status_matches_error(self):
        request_payload = {
            "target_id": "bad_ts_unknown_status",
            "requested_authority": "ANALYZE",
            "requested_delta_a": 0.2,
            "evidence_items": [
                {
                    "evidence_id": "E1",
                    "source": "telemetry",
                    "timestamp": "not-a-timestamp",
                    "data": {"verification_status": "mystery", "confidence": 0.5},
                }
            ],
        }
        with self.assertRaises(ValueError) as py_err:
            self.engine.verify(
                target_id=request_payload["target_id"],
                requested_authority=request_payload["requested_authority"],
                requested_delta_a=request_payload["requested_delta_a"],
                evidence_items=request_payload["evidence_items"],
                current_timestamp="2026-07-14T10:00:00Z",
            )
        node_result = _run_node_verify(request_payload, "2026-07-14T10:00:00Z")
        self.assertFalse(node_result["ok"])
        self.assertIn("timestamp must be an ISO 8601 UTC timestamp", str(py_err.exception))
        self.assertIn("timestamp must be an ISO 8601 UTC timestamp", node_result["error"])


if __name__ == "__main__":
    unittest.main()
