import json
import subprocess
import unittest
from pathlib import Path

from verification_engine.engine import VerificationEngine


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_node_verify(request_payload, current_timestamp):
    node_script = r"""
const fs = require('fs');
const { verifyRequest } = require('./verification_engine/engine');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
try {
  const response = verifyRequest(
    input.target_id,
    input.requested_authority,
    input.requested_delta_a,
    input.evidence_items,
    input.current_timestamp
  );
  process.stdout.write(JSON.stringify({ ok: true, response }));
} catch (err) {
  process.stdout.write(JSON.stringify({ ok: false, error: err.message }));
}
"""
    payload = dict(request_payload)
    payload["current_timestamp"] = current_timestamp
    proc = subprocess.run(
        ["node", "-e", node_script],
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


if __name__ == "__main__":
    unittest.main()
