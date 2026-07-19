#!/usr/bin/env python3
"""Generate an internal verification report from deterministic simulation output."""

import json
from pathlib import Path
from nexus_simulation import run_simulation


def main() -> int:
    result = run_simulation()
    report = {
        "report_type": "internal_verification_report",
        "actual_constraint_violations": result["summary"]["constraint_violations"],
        "final_verification_debt": result["ve_summary"]["VDebt_Final"],
        "no_drift": bool(all(result["success"].values())),
        "cycles": result["cycles"],
    }

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / "internal_verification_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"actual_constraint_violations: {report['actual_constraint_violations']}")
    print(f"final_verification_debt: {report['final_verification_debt']}")
    print(f"report_path: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
