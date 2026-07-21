import json
import unittest
from pathlib import Path


class TestBridgeSchemas(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_request_schema_exists_and_has_required_fields(self):
        schema_path = self.root / "schemas" / "tglr_bridge_request.schema.json"
        self.assertTrue(schema_path.exists())
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema["required"])
        for field in [
            "request_id",
            "source_book_id",
            "receiver_book_id",
            "state_id",
            "parent_state_ids",
            "target_id",
            "requested_delta_a",
            "requested_authority",
            "evaluation_timestamp",
            "evidence_items",
        ]:
            self.assertIn(field, required)

    def test_response_schema_exists_and_exposes_engine_response(self):
        schema_path = self.root / "schemas" / "tglr_bridge_response.schema.json"
        self.assertTrue(schema_path.exists())
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertIn("engine_response", schema["properties"])
        self.assertIn("admission_status", schema["properties"])


if __name__ == "__main__":
    unittest.main()
