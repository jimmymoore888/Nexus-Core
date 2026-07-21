import json
import subprocess
import unittest
from pathlib import Path

from tglr_bridge import TGLRBridge


class TestBridgeParity(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def _node_bridge(self, payload):
        node = subprocess.run(
            ["node", str(self.root / "tests" / "node_bridge_wrapper.js")],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
            cwd=str(self.root),
        )
        return json.loads(node.stdout)

    def _request(self):
        return {
            "request_id": "REQ-PARITY-001",
            "source_book_id": "BOOK-A",
            "receiver_book_id": "BOOK-A",
            "state_id": "STATE-PARITY-001",
            "parent_state_ids": ["U0"],
            "target_id": "system_001",
            "requested_delta_a": 0.3,
            "requested_authority": "ANALYZE",
            "evaluation_timestamp": "2026-07-20T00:00:00Z",
            "evidence_items": [
                {
                    "evidence_id": "EVD-001",
                    "source": "telemetry",
                    "timestamp": "2026-07-19T23:59:59Z",
                    "data": {"verification_status": "valid", "confidence": 0.95},
                }
            ],
        }

    def test_grant_parity(self):
        payload = self._request()
        py = TGLRBridge().verify(payload)
        node = self._node_bridge(payload)
        self.assertTrue(node["ok"])
        self.assertEqual(py, node["response"])

    def test_malformed_parity(self):
        payload = self._request()
        payload["requested_delta_a"] = "bad"
        with self.assertRaisesRegex(ValueError, "requested_delta_a"):
            TGLRBridge().verify(payload)
        node = self._node_bridge(payload)
        self.assertFalse(node["ok"])
        self.assertIn("requested_delta_a", node["error"])


if __name__ == "__main__":
    unittest.main()
