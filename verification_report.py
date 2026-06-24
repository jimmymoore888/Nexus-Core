from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import struct
import zlib
from typing import Dict, Iterable, List, Sequence, Tuple


REPORT_DIR_DEFAULT = "reports"
SUMMARY_JSON = "verification_summary.json"
REPORT_MD = "verification_report.md"


def _to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx = _mean(xs)
    my = _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    den = den_x * den_y
    if den <= 1e-12:
        return 0.0
    return num / den


def _classify_trend(values: Sequence[float]) -> str:
    if not values:
        return "stable"
    n = len(values)
    window = max(1, n // 20)
    start_mean = _mean(values[:window])
    end_mean = _mean(values[-window:])
    delta = end_mean - start_mean
    dynamic = max(abs(max(values) - min(values)), 1e-9)
    rel = delta / dynamic
    if rel > 0.03:
        return "upward"
    if rel < -0.03:
        return "downward"
    return "stable"


def _chunk_ranges(flags: Sequence[int], cycles: Sequence[int]) -> List[str]:
    if not flags or not cycles:
        return []
    ranges: List[str] = []
    start = None
    prev = None
    for i, active in enumerate(flags):
        if active and start is None:
            start = cycles[i]
            prev = cycles[i]
        elif active and start is not None:
            prev = cycles[i]
        elif not active and start is not None and prev is not None:
            ranges.append(f"{start}-{prev}")
            start = None
            prev = None
    if start is not None and prev is not None:
        ranges.append(f"{start}-{prev}")
    return ranges


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _write_png(path: str, width: int, height: int, rgb: bytes) -> None:
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])
    idat = zlib.compress(bytes(raw), level=9)
    data = header + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(data)


def _downsample(values: Sequence[float], target: int) -> List[float]:
    if not values:
        return []
    if len(values) <= target:
        return list(values)
    out: List[float] = []
    block = len(values) / target
    for i in range(target):
        lo = int(i * block)
        hi = int((i + 1) * block)
        hi = max(hi, lo + 1)
        hi = min(hi, len(values))
        out.append(_mean(values[lo:hi]))
    return out


def _draw_line_chart(path: str, values: Sequence[float], title: str) -> None:
    width, height = 1200, 420
    margin_l, margin_r, margin_t, margin_b = 56, 24, 24, 36
    chart_w = width - margin_l - margin_r
    chart_h = height - margin_t - margin_b

    pixels = bytearray([255] * (width * height * 3))

    def set_px(x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 3
            pixels[idx : idx + 3] = bytes((r, g, b))

    def draw_line(x0: int, y0: int, x1: int, y1: int, color: Tuple[int, int, int]) -> None:
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            set_px(x0, y0, *color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    for x in range(margin_l, width - margin_r):
        set_px(x, height - margin_b, 0, 0, 0)
    for y in range(margin_t, height - margin_b):
        set_px(margin_l, y, 0, 0, 0)

    data = _downsample(values, chart_w)
    if not data:
        _write_png(path, width, height, bytes(pixels))
        return

    ymin = min(data)
    ymax = max(data)
    if abs(ymax - ymin) < 1e-12:
        ymin -= 0.5
        ymax += 0.5

    prev = None
    for i, v in enumerate(data):
        x = margin_l + i
        y = margin_t + int((ymax - v) * (chart_h - 1) / (ymax - ymin))
        if prev is not None:
            draw_line(prev[0], prev[1], x, y, (31, 119, 180))
        prev = (x, y)

    # lightweight title marker band
    for x in range(8, min(8 + len(title) * 5, width - 8)):
        set_px(x, 8, 70, 70, 70)

    _write_png(path, width, height, bytes(pixels))


def load_telemetry(csv_path: str) -> List[Dict[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def generate_reports(csv_path: str = "nexus_telemetry.csv", report_dir: str = REPORT_DIR_DEFAULT) -> Dict[str, object]:
    rows = load_telemetry(csv_path)
    if not rows:
        raise ValueError("nexus_telemetry.csv is empty")

    os.makedirs(report_dir, exist_ok=True)

    cycles: List[int] = []
    da_dv_ratio: List[float] = []
    utilization: List[float] = []
    reserve: List[float] = []
    debt: List[float] = []
    governance: List[int] = []
    governance_increments: List[int] = []
    recursion_proxy_cumulative: List[int] = []
    recursion_proxy_increment: List[int] = []
    truth_score: List[float] = []
    accuracy_score: List[float] = []

    previous_governance = 0
    recursion_total = 0
    for row in rows:
        cycle = _to_int(row.get("Cycle"), len(cycles) + 1)
        dv = _to_float(row.get("delta_v_budget"), 0.0)
        da = _to_float(row.get("delta_a_granted"), 0.0)
        ratio = (da / dv) if dv > 0 else 0.0
        util = _to_float(row.get("verification_utilization_pct"), ratio)
        rsv = _to_float(row.get("verification_reserve"), 0.0)
        dbt = _to_float(row.get("verification_debt"), 0.0)
        gov = _to_int(row.get("governance_interventions"), 0)
        a_n = _to_float(row.get("A(n)"), 0.0)
        delta_a = _to_float(row.get("ΔA"), 0.0)
        rec_inc = 1 if abs(a_n) >= 2.999999 and delta_a > 0 else 0
        recursion_total += rec_inc

        cycles.append(cycle)
        da_dv_ratio.append(ratio)
        utilization.append(util)
        reserve.append(rsv)
        debt.append(dbt)
        governance.append(gov)
        governance_increments.append(max(0, gov - previous_governance))
        recursion_proxy_increment.append(rec_inc)
        recursion_proxy_cumulative.append(recursion_total)
        truth_score.append(_to_float(row.get("Truth Score"), 0.0))
        accuracy_score.append(_to_float(row.get("Accuracy Score"), 0.0))

        previous_governance = gov

    max_da_dv_ratio = max(da_dv_ratio) if da_dv_ratio else 0.0
    mean_da_dv_ratio = _mean(da_dv_ratio)
    final_verification_reserve = reserve[-1] if reserve else 0.0
    final_verification_debt = debt[-1] if debt else 0.0
    governance_intervention_rate = (governance[-1] / len(cycles)) if cycles else 0.0
    actual_constraint_violations = _to_int(rows[-1].get("actual_constraint_violations"), 0)

    ratio_trend = _classify_trend(da_dv_ratio)
    reserve_trend = _classify_trend(reserve)
    ratio_approach_one = max_da_dv_ratio >= 0.90
    debt_created = max(debt) > 0 if debt else False

    nonzero_governance = [1 if x > 0 else 0 for x in governance_increments]
    governance_ranges = _chunk_ranges(nonzero_governance, cycles)

    recursion_util_corr = _pearson(
        [float(x) for x in recursion_proxy_increment],
        utilization,
    )
    recursion_corr_text = (
        "positive" if recursion_util_corr > 0.2 else "negative" if recursion_util_corr < -0.2 else "weak"
    )

    truth_acc_corr = _pearson(truth_score, accuracy_score)
    truth_acc_abs_diff = _mean([abs(t - a) for t, a in zip(truth_score, accuracy_score)])
    truth_accuracy_aligned = truth_acc_corr > 0.9 and truth_acc_abs_diff < 0.06

    chart_map = {
        "da_dv_ratio_trend.png": da_dv_ratio,
        "verification_reserve_trend.png": reserve,
        "verification_debt_trend.png": debt,
        "verification_utilization_trend.png": utilization,
        "governance_interventions_trend.png": [float(x) for x in governance],
        "recursion_events_trend.png": [float(x) for x in recursion_proxy_cumulative],
        "truth_score_trend.png": truth_score,
        "accuracy_score_trend.png": accuracy_score,
    }

    for filename, series in chart_map.items():
        _draw_line_chart(os.path.join(report_dir, filename), series, filename)

    summary = {
        "cycles": len(cycles),
        "max_da_dv_ratio": max_da_dv_ratio,
        "mean_da_dv_ratio": mean_da_dv_ratio,
        "final_verification_reserve": final_verification_reserve,
        "final_verification_debt": final_verification_debt,
        "governance_intervention_rate": governance_intervention_rate,
        "actual_constraint_violations": actual_constraint_violations,
        "ratio_trend": ratio_trend,
        "ratio_approach_one": ratio_approach_one,
        "debt_created": debt_created,
        "reserve_trend": reserve_trend,
        "governance_cluster_ranges": governance_ranges,
        "recursion_utilization_correlation": recursion_util_corr,
        "truth_accuracy_correlation": truth_acc_corr,
        "truth_accuracy_mean_abs_diff": truth_acc_abs_diff,
        "truth_accuracy_aligned": truth_accuracy_aligned,
        "recursion_events_proxy_final": recursion_proxy_cumulative[-1] if recursion_proxy_cumulative else 0,
    }

    summary_path = os.path.join(report_dir, SUMMARY_JSON)
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    governance_text = ", ".join(governance_ranges[:8]) if governance_ranges else "none"
    md_lines = [
        "# Nexus Verification Engineering Report",
        "",
        f"- Cycles analyzed: {len(cycles)}",
        f"- max_da_dv_ratio: {max_da_dv_ratio:.6f}",
        f"- mean_da_dv_ratio: {mean_da_dv_ratio:.6f}",
        f"- final_verification_reserve: {final_verification_reserve:.6f}",
        f"- final_verification_debt: {final_verification_debt:.6f}",
        f"- governance_intervention_rate: {governance_intervention_rate:.6f}",
        f"- actual_constraint_violations: {actual_constraint_violations}",
        "",
        "## Engineering Answers",
        "",
        f"- Did ΔA/ΔV trend upward, downward, or remain stable? **{ratio_trend}**",
        f"- Did the ratio ever approach 1.0? **{'Yes' if ratio_approach_one else 'No'}** (max={max_da_dv_ratio:.6f})",
        f"- Was verification debt ever created? **{'Yes' if debt_created else 'No'}**",
        f"- Did verification reserve grow, shrink, or stabilize? **{reserve_trend}**",
        f"- Did governance interventions cluster in specific cycle ranges? **{'Yes' if governance_ranges else 'No'}** ({governance_text})",
        f"- Did recursion events correlate with utilization? **{recursion_corr_text} correlation** (r={recursion_util_corr:.6f})",
        f"- Did truth score and accuracy score remain aligned? **{'Yes' if truth_accuracy_aligned else 'No'}** (corr={truth_acc_corr:.6f}, mean_abs_diff={truth_acc_abs_diff:.6f})",
    ]

    report_path = os.path.join(report_dir, REPORT_MD)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines) + "\n")

    return {
        "summary": summary,
        "summary_path": summary_path,
        "report_path": report_path,
        "chart_files": [os.path.join(report_dir, name) for name in chart_map],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Nexus verification engineering reports")
    parser.add_argument("--input", default="nexus_telemetry.csv", help="Path to telemetry CSV")
    parser.add_argument("--output-dir", default=REPORT_DIR_DEFAULT, help="Output directory for report artifacts")
    args = parser.parse_args()

    results = generate_reports(csv_path=args.input, report_dir=args.output_dir)
    summary = results["summary"]
    print(f"max_da_dv_ratio={summary['max_da_dv_ratio']:.6f}")
    print(f"mean_da_dv_ratio={summary['mean_da_dv_ratio']:.6f}")
    print(f"final_verification_reserve={summary['final_verification_reserve']:.6f}")
    print(f"final_verification_debt={summary['final_verification_debt']:.6f}")


if __name__ == "__main__":
    main()
