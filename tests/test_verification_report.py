import csv
import os
import subprocess
import tempfile
import unittest

from nexus_simulation import run_simulation
from verification_report import generate_reports


class VerificationReportTests(unittest.TestCase):
    def _write_csv(self, path: str, cycles: int = 1000) -> None:
        result = run_simulation(cycles=cycles, seed=7)
        flat_rows = []
        for row in result["telemetry"]:
            flat = {}
            for key, val in row.items():
                if key == "Weight Distribution":
                    for src, w in val.items():
                        flat[f"weight_{src}"] = w
                else:
                    flat[key] = val
            flat_rows.append(flat)

        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(flat_rows[0].keys()))
            writer.writeheader()
            writer.writerows(flat_rows)

    def test_generate_reports_creates_all_outputs_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "nexus_telemetry.csv")
            out_dir = os.path.join(tmpdir, "reports")
            self._write_csv(csv_path)

            result = generate_reports(csv_path=csv_path, report_dir=out_dir)
            summary = result["summary"]

            expected = [
                "da_dv_ratio_trend.png",
                "verification_reserve_trend.png",
                "verification_debt_trend.png",
                "verification_utilization_trend.png",
                "governance_interventions_trend.png",
                "recursion_events_trend.png",
                "truth_score_trend.png",
                "accuracy_score_trend.png",
                "verification_summary.json",
                "verification_report.md",
            ]
            for name in expected:
                self.assertTrue(os.path.isfile(os.path.join(out_dir, name)), msg=name)

            self.assertLess(summary["max_da_dv_ratio"], 1.0)
            self.assertEqual(summary["actual_constraint_violations"], 0)
            self.assertEqual(summary["final_verification_debt"], 0.0)

    def test_script_runs_successfully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "nexus_telemetry.csv")
            out_dir = os.path.join(tmpdir, "reports")
            self._write_csv(csv_path, cycles=500)

            cmd = [
                "python",
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "verification_report.py")),
                "--input",
                csv_path,
                "--output-dir",
                out_dir,
            ]
            completed = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("max_da_dv_ratio=", completed.stdout)
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "verification_report.md")))


if __name__ == "__main__":
    unittest.main()
