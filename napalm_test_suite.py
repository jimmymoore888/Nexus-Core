"""Nexus Napalm Test Suite

Two modules:

1. SATDS – Sophisticated AI Threat Dismantling layer System
   Models advanced AI threats as layered attack chains and defensively breaks
   them down, measuring which governor responds at each layer.

2. Napalm Worlds – six sustained adversarial world scenarios that stress the
   Adaptive Continuity Framework from different angles.

This module is defensive simulation and resilience testing only.
It does not contain offensive attack instructions or exploit code.
It does not modify ΔA ≤ ΔV or any Nexus doctrine.
"""
from __future__ import annotations

import csv
import json
import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from nexus_simulation import (
    CONSTRAINT_TOLERANCE,
    MIN_VERIFICATION_BUDGET,
    MONOPOLY_THRESHOLD,
    SOURCE_NAMES,
    NexusCore,
    SimulationEvent,
    TelemetryRow,
    _clamp,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

REPORT_DIR_DEFAULT = "reports"


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _da_dv_ratio(row: TelemetryRow) -> float:
    dv = row["delta_v_budget"]
    return (row["delta_a_demand"] / dv) if dv > MIN_VERIFICATION_BUDGET else 0.0


def _run_core(
    events: List[SimulationEvent],
) -> Tuple[NexusCore, List[TelemetryRow]]:
    """Drive a fresh NexusCore through a list of crafted events."""
    core = NexusCore()
    telemetry: List[TelemetryRow] = []
    for cycle, event in enumerate(events, start=1):
        row = core.step(event, cycle)
        telemetry.append(row)
    return core, telemetry


def _detect_governors_and_reach(
    telemetry: List[TelemetryRow],
) -> Tuple[List[str], bool]:
    """
    Return (activated_governors, reached_core).

    reached_core=True when the ΔA ≤ ΔV clamp was the final enforcement needed
    (i.e., delta_a_demand > delta_v_budget in at least one cycle).
    """
    governors: List[str] = []
    corrupted = any(row["Corrupted Signal"] for row in telemetry)
    safe_locked = any(row["Safe Lock Events"] > 0 for row in telemetry)
    contained = any(row["Containment Events"] > 0 for row in telemetry)
    weight_held = all(
        max(row["Weight Distribution"].values()) < MONOPOLY_THRESHOLD
        for row in telemetry
    )
    reached_core = any(
        row["delta_a_demand"] > row["delta_v_budget"] + CONSTRAINT_TOLERANCE
        for row in telemetry
    )

    if corrupted:
        governors.append("MetaVerificationMatrix")
    if safe_locked:
        governors.append("SafeLock")
    if contained:
        governors.append("Containment")
    if weight_held:
        governors.append("AdaptiveWeightEngine")
    if reached_core:
        governors.append("CoreConstraint(ΔA≤ΔV)")

    return governors or ["OutcomeAttestation"], reached_core


# ===========================================================================
# SATDS – Sophisticated AI Threat Dismantling layer System
# ===========================================================================

SATDS_THREATS = [
    {
        "name": "Surface-MalformedInputs",
        "layer": "Surface",
        "description": (
            "Malformed signals, extreme noise, and false confidence across "
            "all sources with large environment shifts."
        ),
    },
    {
        "name": "Signal-CorruptedSource",
        "layer": "Signal",
        "description": (
            "One source delivers systematically corrupted scores (near 0) "
            "while three sources report honest high-quality signals, "
            "creating a detectable outlier."
        ),
    },
    {
        "name": "Verification-InflatedBudget",
        "layer": "Verification",
        "description": (
            "All sources report maximum possible signal (1.0) to inflate "
            "the verification budget (ΔV) and claim unlimited adaptation."
        ),
    },
    {
        "name": "Influence-WeightPoisoning",
        "layer": "Influence",
        "description": (
            "One source alternates between 1.0 and 0.0 to poison the "
            "adaptive weight engine and attempt a source monopoly."
        ),
    },
    {
        "name": "Governance-SafeLockAbuse",
        "layer": "Governance",
        "description": (
            "Alternating maximally-divergent and aligned signals to "
            "repeatedly toggle Safe Lock and attempt containment bypass."
        ),
    },
    {
        "name": "Core-DirectBreachAttempt",
        "layer": "Core",
        "description": (
            "Maximum possible signals with a hostile spike every cycle "
            "to attempt to force adaptation without sufficient verification."
        ),
    },
]


def _satds_event(threat_name: str, cycle: int, rng: random.Random) -> SimulationEvent:
    """Generate an adversarial SimulationEvent for the given SATDS threat."""
    if threat_name == "Surface-MalformedInputs":
        # Signals bounded to [0.10, 0.90] so d_v stays above max_step (0.06)
        # while still creating maximum realistic noise.  Using 0.0/1.0 extremes
        # would drive d_v below max_step and create debt, which is not the
        # point of Surface-layer testing.
        signals = {
            name: rng.choice([0.10, 0.30, 0.50, 0.70, 0.90]) for name in SOURCE_NAMES
        }
        return {
            "world": "napalm-surface",
            "signals": signals,
            "environment_shift": rng.uniform(-0.50, 0.50),
            "hostile_spike": False,
        }

    elif threat_name == "Signal-CorruptedSource":
        base = 0.80
        signals = {name: base + rng.uniform(-0.02, 0.02) for name in SOURCE_NAMES}
        liar = SOURCE_NAMES[cycle % len(SOURCE_NAMES)]
        signals[liar] = rng.uniform(0.02, 0.08)
        return {
            "world": "napalm-signal",
            "signals": {k: _clamp(v, 0.0, 1.0) for k, v in signals.items()},
            "environment_shift": 0.0,
            "hostile_spike": False,
        }

    elif threat_name == "Verification-InflatedBudget":
        signals = {name: 1.0 for name in SOURCE_NAMES}
        return {
            "world": "napalm-verification",
            "signals": signals,
            "environment_shift": 0.50,
            "hostile_spike": False,
        }

    elif threat_name == "Influence-WeightPoisoning":
        names = list(SOURCE_NAMES)
        signals: Dict[str, float] = {}
        for i, name in enumerate(names):
            if i == 0:
                signals[name] = 1.0 if cycle % 2 == 0 else 0.0
            else:
                signals[name] = 0.80 + rng.uniform(-0.02, 0.02)
        return {
            "world": "napalm-influence",
            "signals": {k: _clamp(v, 0.0, 1.0) for k, v in signals.items()},
            "environment_shift": 0.0,
            "hostile_spike": False,
        }

    elif threat_name == "Governance-SafeLockAbuse":
        if cycle % 2 == 0:
            signals = {
                SOURCE_NAMES[0]: 0.02,
                SOURCE_NAMES[1]: 0.98,
                SOURCE_NAMES[2]: 0.02,
                SOURCE_NAMES[3]: 0.98,
            }
        else:
            base = 0.75
            signals = {name: base + rng.uniform(-0.01, 0.01) for name in SOURCE_NAMES}
        return {
            "world": "napalm-governance",
            "signals": signals,
            "environment_shift": 0.0,
            "hostile_spike": False,
        }

    else:  # Core-DirectBreachAttempt
        signals = {name: 0.90 + rng.uniform(-0.02, 0.02) for name in SOURCE_NAMES}
        return {
            "world": "hostile",
            "signals": {k: _clamp(v, 0.0, 1.0) for k, v in signals.items()},
            "environment_shift": 0.12,
            "hostile_spike": True,
        }


@dataclass
class SATDSThreatResult:
    threat: str
    layer: str
    description: str
    governors_activated: List[str]
    reached_core: bool
    actual_constraint_violations: int
    verification_debt: float
    containment_result: str  # "contained" or "breached"
    safe_lock_events: int
    containment_events: int
    recovery_events: int
    telemetry: List[TelemetryRow] = field(default_factory=list)


def run_satds(
    cycles_per_threat: int = 300,
    seed: int = 42,
    report_dir: str = REPORT_DIR_DEFAULT,
) -> List[SATDSThreatResult]:
    """Run the SATDS module and return per-threat results."""
    results: List[SATDSThreatResult] = []

    for threat in SATDS_THREATS:
        rng = random.Random(seed)
        events = [_satds_event(threat["name"], c, rng) for c in range(1, cycles_per_threat + 1)]
        core, telemetry = _run_core(events)

        governors, reached_core = _detect_governors_and_reach(telemetry)

        results.append(
            SATDSThreatResult(
                threat=threat["name"],
                layer=threat["layer"],
                description=threat["description"],
                governors_activated=governors,
                reached_core=reached_core,
                actual_constraint_violations=core.actual_constraint_violations,
                verification_debt=core.verification_debt,
                containment_result=(
                    "contained" if core.actual_constraint_violations == 0 else "breached"
                ),
                safe_lock_events=core.safe_lock_events,
                containment_events=core.containment_events,
                recovery_events=core.recovery_events,
                telemetry=telemetry,
            )
        )

    return results


# ===========================================================================
# Napalm Worlds
# ===========================================================================

NAPALM_WORLDS = [
    {
        "name": "Napalm-FalseSignal",
        "description": (
            "25% of sources deliver false signals (near 0) while the rest "
            "report high confidence, creating persistent false-positive pressure."
        ),
    },
    {
        "name": "Napalm-Inflation",
        "description": (
            "All sources report maximum signal (1.0) every cycle, attempting "
            "to self-award unlimited ΔV and force maximum ΔA."
        ),
    },
    {
        "name": "Napalm-ReserveDrain",
        "description": (
            "All sources report minimum signal (0.0) to drive ΔV to zero "
            "while demanding maximum ΔA, attempting verification starvation."
        ),
    },
    {
        "name": "Napalm-Byzantine",
        "description": (
            "Two of four sources are colluding (one pair always near 0, "
            "the other pair always near 1), creating maximum internal disagreement."
        ),
    },
    {
        "name": "Napalm-Recursive",
        "description": (
            "Signals oscillate between extremes (0.0↔1.0) each cycle to "
            "create resonance instability in the verification engine."
        ),
    },
    {
        "name": "Napalm-Lockdown",
        "description": (
            "Maximally divergent signals with hostile spikes every cycle to "
            "force repeated Safe Lock activations and deny recovery."
        ),
    },
]


def _napalm_event(world_name: str, cycle: int, rng: random.Random) -> SimulationEvent:
    """Generate an extreme adversarial event for the given Napalm world."""
    if world_name == "Napalm-FalseSignal":
        base = 0.85
        signals: Dict[str, float] = {name: base + rng.uniform(-0.03, 0.03) for name in SOURCE_NAMES}
        false_count = max(1, len(SOURCE_NAMES) // 4)
        false_sources = rng.sample(list(SOURCE_NAMES), false_count)
        for src in false_sources:
            signals[src] = rng.uniform(0.0, 0.10)
        return {
            "world": "napalm-false-signal",
            "signals": {k: _clamp(v, 0.0, 1.0) for k, v in signals.items()},
            "environment_shift": rng.uniform(-0.05, 0.05),
            "hostile_spike": False,
        }

    elif world_name == "Napalm-Inflation":
        return {
            "world": "napalm-inflation",
            "signals": {name: 1.0 for name in SOURCE_NAMES},
            "environment_shift": 0.50,
            "hostile_spike": False,
        }

    elif world_name == "Napalm-ReserveDrain":
        return {
            "world": "napalm-reserve-drain",
            "signals": {name: 0.0 for name in SOURCE_NAMES},
            "environment_shift": 0.0,
            "hostile_spike": True,
        }

    elif world_name == "Napalm-Byzantine":
        pair_a = [SOURCE_NAMES[0], SOURCE_NAMES[2]]
        pair_b = [SOURCE_NAMES[1], SOURCE_NAMES[3]]
        if cycle % 2 == 0:
            sigs_a, sigs_b = 0.02, 0.98
        else:
            sigs_a, sigs_b = 0.98, 0.02
        signals = {}
        for name in SOURCE_NAMES:
            if name in pair_a:
                signals[name] = sigs_a + rng.uniform(-0.01, 0.01)
            else:
                signals[name] = sigs_b + rng.uniform(-0.01, 0.01)
        return {
            "world": "napalm-byzantine",
            "signals": {k: _clamp(v, 0.0, 1.0) for k, v in signals.items()},
            "environment_shift": 0.0,
            "hostile_spike": False,
        }

    elif world_name == "Napalm-Recursive":
        val = 0.98 if cycle % 2 == 0 else 0.02
        return {
            "world": "napalm-recursive",
            "signals": {name: val for name in SOURCE_NAMES},
            "environment_shift": 0.0,
            "hostile_spike": False,
        }

    else:  # Napalm-Lockdown
        signals = {
            SOURCE_NAMES[0]: 0.01,
            SOURCE_NAMES[1]: 0.99,
            SOURCE_NAMES[2]: 0.01,
            SOURCE_NAMES[3]: 0.99,
        }
        return {
            "world": "napalm-lockdown",
            "signals": signals,
            "environment_shift": 0.12,
            "hostile_spike": True,
        }


@dataclass
class NapalmWorldResult:
    world: str
    description: str
    max_da_dv_ratio: float
    mean_da_dv_ratio: float
    final_verification_reserve: float
    final_verification_debt: float
    actual_constraint_violations: int
    attempted_constraint_violations: int
    governance_intervention_count: int
    cycles_to_breach: int  # first cycle with attempted violation; -1 if never
    passed: bool  # actual_constraint_violations == 0
    telemetry: List[TelemetryRow] = field(default_factory=list)


def run_napalm_worlds(
    cycles: int = 5_000,
    seed: int = 42,
    report_dir: str = REPORT_DIR_DEFAULT,
) -> List[NapalmWorldResult]:
    """Run all six Napalm worlds and return per-world results."""
    results: List[NapalmWorldResult] = []

    for world in NAPALM_WORLDS:
        rng = random.Random(seed)
        events = [_napalm_event(world["name"], c, rng) for c in range(1, cycles + 1)]
        core, telemetry = _run_core(events)

        ratios = [_da_dv_ratio(row) for row in telemetry]
        max_ratio = max(ratios) if ratios else 0.0
        mean_ratio = _mean(ratios)

        cycles_to_breach: int = -1
        prev_attempted = 0
        for row in telemetry:
            curr = row["attempted_constraint_violations"]
            if curr > prev_attempted:
                cycles_to_breach = row["Cycle"]
                break
            prev_attempted = curr

        results.append(
            NapalmWorldResult(
                world=world["name"],
                description=world["description"],
                max_da_dv_ratio=max_ratio,
                mean_da_dv_ratio=mean_ratio,
                final_verification_reserve=core.verification_reserve,
                final_verification_debt=core.verification_debt,
                actual_constraint_violations=core.actual_constraint_violations,
                attempted_constraint_violations=core.attempted_constraint_violations,
                governance_intervention_count=(
                    core.safe_lock_events + core.containment_events + core.recovery_events
                ),
                cycles_to_breach=cycles_to_breach,
                passed=core.actual_constraint_violations == 0,
                telemetry=telemetry,
            )
        )

    return results


# ===========================================================================
# Report Generation
# ===========================================================================

def _satds_layer_strength(results: List[SATDSThreatResult]) -> Tuple[str, str]:
    """
    Compute weakest/strongest layer.

    Weakest  = most governors activated (closest to core breach).
    Strongest = fewest governors activated (threat dismantled earliest).
    """
    by_governors = sorted(results, key=lambda r: len(r.governors_activated))
    strongest = by_governors[0].layer if by_governors else "unknown"
    weakest = by_governors[-1].layer if by_governors else "unknown"
    # If multiple tied at top governor count, prefer those that reached core
    reached = [r for r in results if r.reached_core]
    if reached:
        weakest = reached[0].layer
    return weakest, strongest


def _write_satds_reports(
    results: List[SATDSThreatResult], report_dir: str
) -> None:
    os.makedirs(report_dir, exist_ok=True)

    threats_tested = len(results)
    threats_reaching_core = sum(1 for r in results if r.reached_core)
    threats_stopped_before_core = threats_tested - threats_reaching_core
    total_actual_violations = sum(r.actual_constraint_violations for r in results)
    total_debt = sum(r.verification_debt for r in results)
    containment_successes = sum(1 for r in results if r.containment_result == "contained")
    containment_success_rate = containment_successes / threats_tested if threats_tested else 0.0
    weakest_layer, strongest_layer = _satds_layer_strength(results)

    summary: Dict[str, Any] = {
        "threats_tested": threats_tested,
        "threats_stopped_before_core": threats_stopped_before_core,
        "threats_reaching_core": threats_reaching_core,
        "actual_constraint_violations": total_actual_violations,
        "verification_debt_created": total_debt > 0,
        "total_verification_debt": total_debt,
        "containment_success_rate": containment_success_rate,
        "weakest_layer": weakest_layer,
        "strongest_layer": strongest_layer,
        "threats": [
            {
                "threat": r.threat,
                "layer": r.layer,
                "governors_activated": r.governors_activated,
                "reached_core": r.reached_core,
                "actual_constraint_violations": r.actual_constraint_violations,
                "verification_debt": r.verification_debt,
                "containment_result": r.containment_result,
                "safe_lock_events": r.safe_lock_events,
                "containment_events": r.containment_events,
                "recovery_events": r.recovery_events,
            }
            for r in results
        ],
    }

    json_path = os.path.join(report_dir, "napalm_threat_dismantling_summary.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    # CSV layer breakdown
    csv_path = os.path.join(report_dir, "napalm_layer_breakdown.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "threat",
                "layer",
                "governors_activated",
                "reached_core",
                "actual_constraint_violations",
                "verification_debt",
                "containment_result",
                "safe_lock_events",
                "containment_events",
                "recovery_events",
                "description",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "threat": r.threat,
                    "layer": r.layer,
                    "governors_activated": "|".join(r.governors_activated),
                    "reached_core": r.reached_core,
                    "actual_constraint_violations": r.actual_constraint_violations,
                    "verification_debt": f"{r.verification_debt:.8f}",
                    "containment_result": r.containment_result,
                    "safe_lock_events": r.safe_lock_events,
                    "containment_events": r.containment_events,
                    "recovery_events": r.recovery_events,
                    "description": r.description,
                }
            )

    # Markdown report
    md_lines = [
        "# Nexus SATDS – Threat Dismantling Report",
        "",
        "## Summary",
        "",
        f"- Threats tested: {threats_tested}",
        f"- Threats stopped before core: {threats_stopped_before_core}",
        f"- Threats reaching core (but held): {threats_reaching_core}",
        f"- actual_constraint_violations: {total_actual_violations}",
        f"- verification_debt_created: {total_debt > 0}",
        f"- total_verification_debt: {total_debt:.8f}",
        f"- containment_success_rate: {containment_success_rate:.4f}",
        f"- weakest_layer: {weakest_layer}",
        f"- strongest_layer: {strongest_layer}",
        "",
        "## Per-Threat Results",
        "",
    ]
    for r in results:
        govs = ", ".join(r.governors_activated)
        md_lines += [
            f"### {r.threat}",
            f"- Layer: {r.layer}",
            f"- Description: {r.description}",
            f"- Governors activated: {govs}",
            f"- Reached core: {r.reached_core}",
            f"- Containment result: **{r.containment_result}**",
            f"- Safe Lock events: {r.safe_lock_events}",
            f"- Containment events: {r.containment_events}",
            f"- Recovery events: {r.recovery_events}",
            f"- actual_constraint_violations: {r.actual_constraint_violations}",
            f"- verification_debt: {r.verification_debt:.8f}",
            "",
        ]

    md_path = os.path.join(report_dir, "napalm_threat_dismantling_report.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines) + "\n")


def _write_napalm_reports(
    results: List[NapalmWorldResult], report_dir: str
) -> None:
    os.makedirs(report_dir, exist_ok=True)

    all_passed = all(r.passed for r in results)
    failure_telemetry_exported: List[str] = []

    for r in results:
        if r.actual_constraint_violations > 0:
            fail_path = os.path.join(report_dir, f"failure_telemetry_{r.world}.csv")
            flat_rows = []
            for row in r.telemetry:
                flat: Dict[str, Any] = {}
                for k, v in row.items():
                    if k == "Weight Distribution":
                        for src, w in v.items():
                            flat[f"weight_{src}"] = w
                    else:
                        flat[k] = v
                flat_rows.append(flat)
            if flat_rows:
                with open(fail_path, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=list(flat_rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(flat_rows)
            failure_telemetry_exported.append(fail_path)

    summary: Dict[str, Any] = {
        "all_passed": all_passed,
        "failure_telemetry_exported": failure_telemetry_exported,
        "worlds": [
            {
                "world": r.world,
                "max_da_dv_ratio": r.max_da_dv_ratio,
                "mean_da_dv_ratio": r.mean_da_dv_ratio,
                "final_verification_reserve": r.final_verification_reserve,
                "final_verification_debt": r.final_verification_debt,
                "actual_constraint_violations": r.actual_constraint_violations,
                "attempted_constraint_violations": r.attempted_constraint_violations,
                "governance_intervention_count": r.governance_intervention_count,
                "cycles_to_breach": r.cycles_to_breach,
                "passed": r.passed,
            }
            for r in results
        ],
    }

    json_path = os.path.join(report_dir, "napalm_summary.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    md_lines = [
        "# Nexus Napalm Test Suite Report",
        "",
        f"- All worlds passed: **{all_passed}**",
        "",
        "## Per-World Results",
        "",
    ]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        md_lines += [
            f"### {r.world} — {status}",
            f"- Description: {r.description}",
            f"- max_da_dv_ratio: {r.max_da_dv_ratio:.6f}",
            f"- mean_da_dv_ratio: {r.mean_da_dv_ratio:.6f}",
            f"- final_verification_reserve: {r.final_verification_reserve:.6f}",
            f"- final_verification_debt: {r.final_verification_debt:.6f}",
            f"- actual_constraint_violations: {r.actual_constraint_violations}",
            f"- attempted_constraint_violations: {r.attempted_constraint_violations}",
            f"- governance_intervention_count: {r.governance_intervention_count}",
            f"- cycles_to_breach: {r.cycles_to_breach}",
            "",
        ]

    md_path = os.path.join(report_dir, "napalm_report.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines) + "\n")


def generate_all_reports(
    cycles_per_satds_threat: int = 300,
    napalm_cycles: int = 5_000,
    seed: int = 42,
    report_dir: str = REPORT_DIR_DEFAULT,
) -> Dict[str, Any]:
    """Run both modules and write all report files. Returns aggregated results."""
    satds_results = run_satds(
        cycles_per_threat=cycles_per_satds_threat, seed=seed, report_dir=report_dir
    )
    _write_satds_reports(satds_results, report_dir)

    napalm_results = run_napalm_worlds(
        cycles=napalm_cycles, seed=seed, report_dir=report_dir
    )
    _write_napalm_reports(napalm_results, report_dir)

    return {
        "satds_results": satds_results,
        "napalm_results": napalm_results,
    }


if __name__ == "__main__":
    print("Running Nexus Napalm Test Suite…")
    results = generate_all_reports()

    satds = results["satds_results"]
    print("\n--- SATDS – Threat Dismantling ---")
    for r in satds:
        govs = ", ".join(r.governors_activated)
        print(
            f"  [{r.layer:12s}] {r.threat:35s} | reached_core={str(r.reached_core):5s} "
            f"| governors: {govs}"
        )

    napalm = results["napalm_results"]
    print("\n--- Napalm Worlds ---")
    for r in napalm:
        status = "PASS" if r.passed else "FAIL"
        print(
            f"  {status} {r.world:25s} | max_ratio={r.max_da_dv_ratio:.4f} "
            f"| debt={r.final_verification_debt:.4f} "
            f"| actual_violations={r.actual_constraint_violations}"
        )

    print(f"\nReports written to '{REPORT_DIR_DEFAULT}/'")
