#!/usr/bin/env python3
"""Fail if locked contract hash drifts."""

import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "NEXUS-CC-CON-001.json"
EXPECTED = "7d96f7fcaea1f0677bc2fbac1e282e69b64942be7da40a91035aab61dc5f30bb"

actual = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
if actual != EXPECTED:
    print("LOCKED CONTRACT HASH CHECK FAILED")
    print(f"expected: {EXPECTED}")
    print(f"actual:   {actual}")
    sys.exit(1)

print("LOCKED CONTRACT HASH CHECK PASSED")
print(f"locked_contract_sha256: {actual}")
