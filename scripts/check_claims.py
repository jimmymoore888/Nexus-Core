#!/usr/bin/env python3
"""Fail if required bounded-claim docs/artifacts are missing."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

required_files = [
    "docs/governance/CONSTITUTION-V02-RECOVERY-GAP.md",
    "docs/governance/LOCKED-CONTRACT-AMBIGUITIES.md",
    "docs/proposals/TGLR-CORE-DEF-001.md",
    "docs/proposals/TGLR-UIR-LAW-001.md",
    "docs/specification/TGLR-END-TO-END-BRIDGE-001.md",
    "schemas/tglr_bridge_request.schema.json",
    "schemas/tglr_bridge_response.schema.json",
    "reports/checksum_manifest.sha256",
    "run_tests.py",
]

required_readme_markers = [
    "SHA-256-DEMO-DIGEST",
    "bounded",
    "does **not** claim",
    "evaluation_timestamp",
]

errors = []
for rel in required_files:
    if not (ROOT / rel).exists():
        errors.append(f"Missing required file: {rel}")

readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
for marker in required_readme_markers:
    if marker.lower() not in readme:
        errors.append(f"README.md missing required bounded-language marker: {marker}")

run_tests = (ROOT / "run_tests.py").read_text(encoding="utf-8")
if "if suite.countTestCases() == 0" not in run_tests:
    errors.append("run_tests.py must fail when zero tests are discovered")

if errors:
    print("CLAIMS/ARTIFACT CHECK FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("CLAIMS/ARTIFACT CHECK PASSED")
