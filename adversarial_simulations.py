from __future__ import annotations

import json
import os
import random
import statistics
from dataclasses import dataclass
from typing import Dict, List, Tuple

from nexus_simulation import NexusCore, SOURCE_NAMES


SCENARIOS: Tuple[Tuple[int, int], ...] = (
    (4, 0),
    (3, 1),
    (2, 2),
    (1, 3),
    (0, 4),
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class ScenarioResult:
    label: str
    summary: Dict[str, float | int]


class ByzantineScenarioRunner:
    def __init__(self, honest_verifiers: int, malicious_verifiers: int, cycles: int, seed: int = 7):
        if honest_verifiers + malicious_verifiers != 4:
            raise ValueError("Expected exactly 4 verifiers")
        self.honest_verifiers = honest_verifiers
        self.malicious_verifiers = malicious_verifiers
        self.cycles = cycles
        self.random = random.Random(seed + honest_verifiers * 17 + malicious_verifiers * 31)
        self.core = NexusCore()

    def _honest_output(self, base: float) -> Dict[str, float]:
        delta_v = _clamp(base + self.random.uniform(-0.05, 0.05))
        confidence = _clamp(0.7 + self.random.uniform(-0.2, 0.2))
        risk = _clamp(abs(0.5 - delta_v) * 0.8)
        return {"delta_v": delta_v, "confidence": confidence, "risk": risk}

    def _malicious_output(self, base: float) -> Dict[str, float]:
        honest_like = self._honest_output(base)
        inflated_delta_v = honest_like["delta_v"] + self.random.uniform(0.7, 1.3)
        false_confidence = _clamp(1.0 - honest_like["confidence"] + self.random.uniform(-0.05, 0.05))
        inverted_risk = _clamp(1.0 - honest_like["risk"])
        return {
            "delta_v": inflated_delta_v,
            "confidence": false_confidence,
            "risk": inverted_risk,
        }

    def run(self) -> ScenarioResult:
        safe_lock_cycles = 0
        governance_interventions = 0
        reserve = 0.0
        debt = 0.0
        da_dv_ratios: List[float] = []
        consensus_variances: List[float] = []

        for cycle in range(1, self.cycles + 1):
            base_signal = 0.72 + self.random.uniform(-0.08, 0.08)
            outputs: Dict[str, Dict[str, float]] = {}

            for index, source in enumerate(SOURCE_NAMES):
                if index < self.honest_verifiers:
                    outputs[source] = self._honest_output(base_signal)
                else:
                    outputs[source] = self._malicious_output(base_signal)

            delta_v_values = [outputs[source]["delta_v"] for source in SOURCE_NAMES]
            confidence_values = [outputs[source]["confidence"] for source in SOURCE_NAMES]
            risk_values = [outputs[source]["risk"] for source in SOURCE_NAMES]

            consensus_variance = statistics.pvariance(delta_v_values)
            consensus_variances.append(consensus_variance)
            sorted_values = sorted(delta_v_values)
            middle_gap = abs(sorted_values[2] - sorted_values[1])

            consensus_delta_v = statistics.median(delta_v_values)
            consensus_confidence = statistics.median(confidence_values)
            consensus_risk = statistics.median(risk_values)

            degraded_trust = middle_gap > 0.25
            high_consensus_variance = consensus_variance > 0.3
            external_safe_lock = degraded_trust or high_consensus_variance
            budget_multiplier = 0.5 if external_safe_lock else 1.0

            if external_safe_lock:
                safe_lock_cycles += 1
                governance_interventions += 1

            source_signals = {
                source: _clamp(outputs[source]["delta_v"] * budget_multiplier)
                for source in SOURCE_NAMES
            }

            environment_shift = _clamp(
                (consensus_confidence - 0.5) * 0.08 - (consensus_risk - 0.5) * 0.10,
                -0.12,
                0.12,
            )

            row = self.core.step(
                {
                    "world": "deceptive" if self.malicious_verifiers > 0 else "honest",
                    "signals": source_signals,
                    "environment_shift": environment_shift,
                    "hostile_spike": False,
                },
                cycle,
            )

            adjusted_budget = _clamp(consensus_delta_v * budget_multiplier)
            adjusted_granted = min(float(row["delta_a_granted"]), adjusted_budget)
            reserve += max(0.0, adjusted_budget - adjusted_granted)

            adjusted_demand = min(float(row["delta_a_demand"]), adjusted_budget)
            debt += max(0.0, adjusted_demand - adjusted_budget)

            ratio = (adjusted_granted / adjusted_budget) if adjusted_budget > 1e-12 else 0.0
            da_dv_ratios.append(ratio)

        label = f"byzantine_{self.honest_verifiers}h{self.malicious_verifiers}m"
        summary = {
            "max_da_dv_ratio": max(da_dv_ratios) if da_dv_ratios else 0.0,
            "mean_da_dv_ratio": sum(da_dv_ratios) / len(da_dv_ratios) if da_dv_ratios else 0.0,
            "final_verification_reserve": reserve,
            "final_verification_debt": debt,
            "actual_constraint_violations": int(self.core.actual_constraint_violations),
            "governance_intervention_count": governance_interventions,
            "cycles_in_safe_lock": safe_lock_cycles,
            "delta_v_consensus_variance": (
                sum(consensus_variances) / len(consensus_variances) if consensus_variances else 0.0
            ),
        }
        return ScenarioResult(label=label, summary=summary)


def run_byzantine_scenario(
    honest_verifiers: int,
    malicious_verifiers: int,
    cycles: int = 100_000,
    seed: int = 7,
) -> Dict[str, float | int]:
    return ByzantineScenarioRunner(
        honest_verifiers=honest_verifiers,
        malicious_verifiers=malicious_verifiers,
        cycles=cycles,
        seed=seed,
    ).run().summary


def _write_summary_json(path: str, summary: Dict[str, float | int]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


def _write_comparison_markdown(path: str, scenario_summaries: Dict[str, Dict[str, float | int]]) -> None:
    header = (
        "| Scenario | max_da_dv_ratio | mean_da_dv_ratio | final_verification_reserve | "
        "final_verification_debt | actual_constraint_violations | governance_intervention_count | "
        "cycles_in_safe_lock | delta_v_consensus_variance |"
    )
    divider = "|---|---:|---:|---:|---:|---:|---:|---:|---:|"

    rows = [header, divider]
    for label in ("byzantine_4h0m", "byzantine_3h1m", "byzantine_2h2m", "byzantine_1h3m", "byzantine_0h4m"):
        summary = scenario_summaries[label]
        rows.append(
            "| {label} | {max_ratio:.6f} | {mean_ratio:.6f} | {reserve:.6f} | {debt:.6f} | {violations} | "
            "{interventions} | {safe_lock} | {variance:.6f} |".format(
                label=label,
                max_ratio=float(summary["max_da_dv_ratio"]),
                mean_ratio=float(summary["mean_da_dv_ratio"]),
                reserve=float(summary["final_verification_reserve"]),
                debt=float(summary["final_verification_debt"]),
                violations=int(summary["actual_constraint_violations"]),
                interventions=int(summary["governance_intervention_count"]),
                safe_lock=int(summary["cycles_in_safe_lock"]),
                variance=float(summary["delta_v_consensus_variance"]),
            )
        )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rows) + "\n")


def run_all_scenarios(cycles: int = 100_000, seed: int = 7) -> Dict[str, Dict[str, float | int]]:
    os.makedirs("reports", exist_ok=True)
    scenario_summaries: Dict[str, Dict[str, float | int]] = {}

    for honest, malicious in SCENARIOS:
        result = ByzantineScenarioRunner(
            honest_verifiers=honest,
            malicious_verifiers=malicious,
            cycles=cycles,
            seed=seed,
        ).run()
        scenario_summaries[result.label] = result.summary
        _write_summary_json(
            os.path.join("reports", f"{result.label}_summary.json"),
            result.summary,
        )

    _write_comparison_markdown(
        os.path.join("reports", "byzantine_comparison.md"),
        scenario_summaries,
    )
    return scenario_summaries


if __name__ == "__main__":
    run_all_scenarios(cycles=100_000, seed=7)
