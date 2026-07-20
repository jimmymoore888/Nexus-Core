#!/usr/bin/env python3
"""Fail if required version strings are not aligned."""

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent

errors = []

pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
if pkg.get("version") != "1.4.0-beta.1":
    errors.append("package.json version must be 1.4.0-beta.1")

readme = (ROOT / "README.md").read_text(encoding="utf-8")
if "v1.4.0-beta.1" not in readme:
    errors.append("README.md must reference v1.4.0-beta.1")
if "v0.1.1" not in readme:
    errors.append("README.md must reference engine v0.1.1")

py_init = (ROOT / "verification_engine" / "__init__.py").read_text(encoding="utf-8")
if not re.search(r"__version__\s*=\s*['\"]0\.1\.1['\"]", py_init):
    errors.append("verification_engine/__init__.py must set __version__ to 0.1.1")

if errors:
    print("VERSION CHECK FAILED")
    for e in errors:
        print(f"- {e}")
    sys.exit(1)

print("VERSION CHECK PASSED")
