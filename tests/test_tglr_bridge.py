import unittest

from tglr_bridge import TGLRBridge, DEMONSTRATION_SCOPE, escape_html


def _valid_evidence():
    return [
        {
            "evidence_id": "EVD-001",
            "source": "telemetry",
            "timestamp": "2026-07-19T23:59:59Z",
            "data": {"verification_status": "valid", "confidence": 0.95},
        }
    ]


class TestTGLRBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = TGLRBridge()
        self.base = {
            "request_id": "REQ-001",
            "source_book_id": "BOOK-A",
            "receiver_book_id": "BOOK-A",
            "state_id": "STATE-001",
            "parent_state_ids": ["U0"],
            "target_id": "system_001",
            "requested_delta_a": 0.3,
            "requested_authority": "ANALYZE",
            "evaluation_timestamp": "2026-07-20T00:00:00Z",
            "evidence_items": _valid_evidence(),
        }

    def test_grant_front_to_back_to_front(self):
        response = self.bridge.verify(dict(self.base))
        self.assertEqual(response["decision"], "GRANT")
        self.assertEqual(response["admission_status"], "ADMITTED")
        self.assertEqual(response["demonstration_scope"], DEMONSTRATION_SCOPE)
        self.assertEqual(response["engine_response"]["validated_delta_a"], self.base["requested_delta_a"])
        self.assertLessEqual(response["engine_response"]["validated_delta_a"], response["engine_response"]["delta_v"])

    def test_reject_does_not_admit(self):
        req = dict(self.base)
        req["request_id"] = "REQ-002"
        req["state_id"] = "STATE-002"
        req["evidence_items"] = [
            {
                "evidence_id": "EVD-002",
                "source": "telemetry",
                "timestamp": "2026-07-19T23:59:59Z",
                "data": {"verification_status": "invalid", "confidence": 0.1},
            }
        ]
        response = self.bridge.verify(req)
        self.assertEqual(response["decision"], "REJECT")
        self.assertEqual(response["admission_status"], "REJECTED")

    def test_safe_lock_does_not_admit(self):
        req = dict(self.base)
        req["request_id"] = "REQ-003"
        req["state_id"] = "STATE-003"
        req["requested_delta_a"] = 0.95
        response = self.bridge.verify(req)
        self.assertEqual(response["decision"], "SAFE_LOCK")
        self.assertEqual(response["admission_status"], "REJECTED")

    def test_duplicate_request_id_rejected(self):
        self.bridge.verify(dict(self.base))
        req = dict(self.base)
        req["state_id"] = "STATE-004"
        response = self.bridge.verify(req)
        self.assertEqual(response["admission_status"], "REJECTED")
        self.assertIn("Duplicate request_id", response["reason"])

    def test_unauthorized_cross_book_rejected(self):
        req = dict(self.base)
        req["request_id"] = "REQ-005"
        req["state_id"] = "STATE-005"
        req["source_book_id"] = "BOOK-B"
        response = self.bridge.verify(req)
        self.assertEqual(response["decision"], "REJECT")
        self.assertIn("Unauthorized cross-Book", response["reason"])

    def test_orphan_parent_rejected(self):
        req = dict(self.base)
        req["request_id"] = "REQ-006"
        req["state_id"] = "STATE-006"
        req["parent_state_ids"] = ["NOPE"]
        response = self.bridge.verify(req)
        self.assertEqual(response["admission_status"], "REJECTED")
        self.assertIn("Orphan/nonexistent parent", response["reason"])

    def test_malformed_request_raises_value_error(self):
        req = dict(self.base)
        req["request_id"] = "REQ-007"
        req["requested_delta_a"] = "0.3"
        with self.assertRaisesRegex(ValueError, "requested_delta_a"):
            self.bridge.verify(req)

    def test_deterministic_same_input_same_output(self):
        bridge = TGLRBridge()
        req = dict(self.base)
        req["request_id"] = "REQ-008"
        req["state_id"] = "STATE-008"
        first = bridge.verify(req)

        bridge2 = TGLRBridge()
        second = bridge2.verify(req)
        self.assertEqual(first, second)

    def test_html_escaping(self):
        escaped = escape_html('<script>alert("x")</script>')
        self.assertEqual(escaped, "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;")

    def test_growth_proxy_100_states_and_connectivity(self):
        parent = "U0"
        for i in range(1, 101):
            req = dict(self.base)
            req["request_id"] = f"REQ-G-{i}"
            req["state_id"] = f"STATE-G-{i}"
            req["parent_state_ids"] = [parent]
            req["evidence_items"] = [
                {
                    "evidence_id": f"EVD-G-{i}",
                    "source": "telemetry",
                    "timestamp": "2026-07-19T23:59:59Z",
                    "data": {"verification_status": "valid", "confidence": 0.99},
                }
            ]
            res = self.bridge.verify(req)
            self.assertEqual(res["admission_status"], "ADMITTED")
            self.assertTrue(res["lineage"]["connected_to_u0"])
            self.assertEqual(res["lineage"]["generation"], i)
            parent = req["state_id"]


if __name__ == "__main__":
    unittest.main()
