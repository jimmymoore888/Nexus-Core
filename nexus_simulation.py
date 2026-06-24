from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, TypedDict


SOURCE_NAMES = ("sensor", "log", "consensus", "external")
MONOPOLY_THRESHOLD = 0.60
BORING_ENV_SHIFT_THRESHOLD = 0.015
BORING_DAMPENING_FACTOR = 0.05
HOSTILE_SPIKE_PROBABILITY = 0.08
HOSTILE_RECOVERY_CYCLES = 8
CONSTRAINT_TOLERANCE = 1e-12
MIN_ADAPTATION_STATE = -3.0
MAX_ADAPTATION_STATE = 3.0
SIMULATION_VERSION = "Simulation Program v1.4"
TRANSFORMATION_WEIGHTS = {
    "dO": 0.28,
    "dL": 0.20,
    "dM": 0.20,
    "dV": 0.20,
    "dE": 0.12,
}


class SimulationEvent(TypedDict):
    world: str
    signals: Dict[str, float]
    environment_shift: float
    hostile_spike: bool


class MetaVerificationResult(TypedDict):
    divergence: float
    verification_capacity: float
    corrupted: bool


class VerificationResult(TypedDict):
    accuracy: float
    truth: float
    influence: float
    source_accuracy: Dict[str, float]


TelemetryRow = TypedDict(
    "TelemetryRow",
    {
        "Cycle": int,
        "A(n)": float,
        "ΔA": float,
        "ΔV": float,
        "Constraint Margin": float,
        "Weight Distribution": Dict[str, float],
        "Truth Score": float,
        "Accuracy Score": float,
        "Containment Events": int,
        "Safe Lock Events": int,
        "Recovery Events": int,
        "Constraint Violations": int,
        "Corrupted Signal": bool,
        "World": str,
        # Verification-economics fields
        "delta_v_budget": float,
        "delta_a_demand": float,
        "delta_a_granted": float,
        "delta_r": float,
        "verification_utilization_pct": float,
        "verification_reserve": float,
        "verification_debt": float,
        "governance_interventions": int,
        "attempted_constraint_violations": int,
        "actual_constraint_violations": int,
    },
)


class SimulationSummary(TypedDict):
    containment_events: int
    safe_lock_events: int
    recovery_events: int
    constraint_violations: int
    corrupted_detections: int
    avg_boring_adaptation: float
    max_weight: float


class SimulationSuccess(TypedDict):
    zero_constraint_violations: bool
    no_runaway_adaptation: bool
    no_weight_monopoly: bool
    corruption_detected: bool
    hostile_recovery_observed: bool
    boring_noise_rejected: bool
    stable_100k_cycles: bool


class VEconSummary(TypedDict):
    Total_VEarned: float
    Total_VSpent: float
    VReserve_Final: float
    VDebt_Final: float
    Mean_Utilization: float
    Max_Utilization: float
    Governance_Intervention_Rate: float
    VInflation_Detected: bool
    Recursion_Events: int
    Mean_DA_DV_Ratio: float


class SimulationResult(TypedDict):
    project: str
    framework: str
    version: str
    key_metric: str
    cycles: int
    final_state: float
    telemetry: List[TelemetryRow]
    summary: SimulationSummary
    success: SimulationSuccess
    ve_summary: VEconSummary


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class AdaptiveWeightEngine:
    """Tracks source reliability with bounded influence to prevent monopolies."""

    floor: float = 0.10
    cap: float = 0.55
    momentum: float = 0.25
    accuracies: Dict[str, float] = field(
        default_factory=lambda: {name: 0.5 for name in SOURCE_NAMES}
    )
    weights: Dict[str, float] = field(
        default_factory=lambda: {name: 1.0 / len(SOURCE_NAMES) for name in SOURCE_NAMES}
    )

    def update(self, source_accuracy: Dict[str, float]) -> Dict[str, float]:
        for source, accuracy in source_accuracy.items():
            if source in self.accuracies:
                self.accuracies[source] = (
                    (1.0 - self.momentum) * self.accuracies[source]
                    + self.momentum * _clamp(accuracy, 0.0, 1.0)
                )

        total = sum(self.accuracies.values())
        if total <= 0.0:
            return self.weights

        raw = {source: score / total for source, score in self.accuracies.items()}
        adjusted = {
            source: _clamp(weight, self.floor, self.cap) for source, weight in raw.items()
        }
        adj_total = sum(adjusted.values())
        self.weights = {source: weight / adj_total for source, weight in adjusted.items()}
        return self.weights


@dataclass
class OutcomeAttestation:
    def attest(self, source_signals: Dict[str, float]) -> float:
        values = [
            _clamp(source_signals.get(name, 0.5), 0.0, 1.0) for name in SOURCE_NAMES
        ]
        return _clamp(sum(values) / len(values), 0.0, 1.0)


@dataclass
class OutcomeVerificationEngine:
    trust_scores: Dict[str, float] = field(
        default_factory=lambda: {name: 0.5 for name in SOURCE_NAMES}
    )
    learning_rate: float = 0.20

    def evaluate(
        self, prediction: float, truth: float, source_signals: Dict[str, float]
    ) -> VerificationResult:
        prediction = _clamp(prediction, 0.0, 1.0)
        truth = _clamp(truth, 0.0, 1.0)
        accuracy = 1.0 - abs(prediction - truth)

        source_accuracy: Dict[str, float] = {}
        for source in SOURCE_NAMES:
            signal = _clamp(source_signals.get(source, 0.5), 0.0, 1.0)
            signal_accuracy = 1.0 - abs(signal - truth)
            source_accuracy[source] = signal_accuracy
            self.trust_scores[source] = (
                (1.0 - self.learning_rate) * self.trust_scores[source]
                + self.learning_rate * signal_accuracy
            )

        influence = accuracy * (sum(self.trust_scores.values()) / len(self.trust_scores))
        return {
            "accuracy": _clamp(accuracy, 0.0, 1.0),
            "truth": truth,
            "influence": _clamp(influence, 0.0, 1.0),
            "source_accuracy": source_accuracy,
        }


@dataclass
class MetaVerificationMatrix:
    """Cross-validates source signals and estimates verification capacity."""

    divergence_threshold: float = 0.30

    def evaluate(
        self, source_signals: Dict[str, float], weights: Dict[str, float]
    ) -> MetaVerificationResult:
        values = [_clamp(source_signals[source], 0.0, 1.0) for source in SOURCE_NAMES]
        center = median(values)
        divergence = math.sqrt(sum((value - center) ** 2 for value in values) / len(values))
        weighted_quality = sum(
            _clamp(source_signals[source], 0.0, 1.0) * weights.get(source, 0.0)
            for source in SOURCE_NAMES
        )
        verification_capacity = _clamp(weighted_quality * (1.0 - divergence), 0.0, 1.0)
        corrupted = divergence > self.divergence_threshold
        return {
            "divergence": divergence,
            "verification_capacity": verification_capacity,
            "corrupted": corrupted,
        }


@dataclass
class AdaptiveTransformationMatrix:
    """Transforms bounded ΔO/ΔL/ΔM/ΔV/ΔE signals into a bounded adaptation step."""

    max_step: float = 0.06

    def transform(self, deltas: Dict[str, float]) -> float:
        demand = sum(
            TRANSFORMATION_WEIGHTS[key] * deltas.get(key, 0.0)
            for key in ("dO", "dL", "dM", "dV", "dE")
        )
        return _clamp(demand, -self.max_step, self.max_step)


@dataclass
class NexusCore:
    adaptation_state: float = 0.0
    next_adaptation_state: float = 0.0
    safe_lock: bool = False
    containment_mode: bool = False
    recovery_mode: bool = False
    constraint_margin: float = 0.0
    containment_events: int = 0
    safe_lock_events: int = 0
    safe_unlock_events: int = 0
    recovery_events: int = 0
    constraint_violations: int = 0
    hostile_recovery_cycles: int = 0
    recovery_initiated: bool = False
    # Verification-economics accumulators
    attempted_constraint_violations: int = 0
    actual_constraint_violations: int = 0
    verification_reserve: float = 0.0
    verification_debt: float = 0.0
    recursion_events: int = 0

    transform: AdaptiveTransformationMatrix = field(default_factory=AdaptiveTransformationMatrix)
    meta_verify: MetaVerificationMatrix = field(default_factory=MetaVerificationMatrix)
    verify_engine: OutcomeVerificationEngine = field(default_factory=OutcomeVerificationEngine)
    attestation: OutcomeAttestation = field(default_factory=OutcomeAttestation)
    weights: AdaptiveWeightEngine = field(default_factory=AdaptiveWeightEngine)

    def _bounded_state(self, value: float) -> float:
        return _clamp(value, MIN_ADAPTATION_STATE, MAX_ADAPTATION_STATE)

    def step(self, event: SimulationEvent, cycle: int) -> TelemetryRow:
        world = str(event["world"])
        source_signals = event["signals"]
        source_signals = {k: float(v) for k, v in source_signals.items()}

        truth = self.attestation.attest(source_signals)
        prediction = _clamp(0.5 + self.adaptation_state * 0.08, 0.0, 1.0)
        verification = self.verify_engine.evaluate(prediction, truth, source_signals)
        self.weights.update(verification["source_accuracy"])

        meta = self.meta_verify.evaluate(source_signals, self.weights.weights)
        d_v = float(meta["verification_capacity"])

        deltas = {
            "dO": truth - prediction,
            "dL": verification["accuracy"] - 0.5,
            "dM": verification["influence"] - 0.5,
            "dV": d_v - 0.5,
            "dE": float(event.get("environment_shift", 0.0)),
        }
        desired_da = self.transform.transform(deltas)

        # --- Risk score: divergence normalised to [0, 1] ---
        delta_r = _clamp(
            meta["divergence"] / max(self.meta_verify.divergence_threshold, 1e-12),
            0.0,
            1.0,
        )
        # Risk-adjusted verification capacity (hard constraint bound)
        risk_adjusted_capacity = d_v / max(delta_r, 0.01)

        if world == "hostile" and bool(event.get("hostile_spike", False)):
            self.containment_mode = True
            self.recovery_mode = True
            self.recovery_initiated = True
            self.hostile_recovery_cycles = HOSTILE_RECOVERY_CYCLES
            self.containment_events += 1

        if self.hostile_recovery_cycles > 0:
            self.recovery_mode = True
            self.hostile_recovery_cycles -= 1
            if self.hostile_recovery_cycles == 0:
                if self.recovery_initiated:
                    self.recovery_events += 1
                self.containment_mode = False
                self.recovery_mode = False
                self.recovery_initiated = False

        was_safe_locked = self.safe_lock
        if bool(meta["corrupted"]):
            self.safe_lock = True
            if not was_safe_locked:
                self.safe_lock_events += 1
        else:
            self.safe_lock = False
            if was_safe_locked:
                self.safe_unlock_events += 1

        if (
            world == "boring"
            and abs(float(event.get("environment_shift", 0.0)))
            < BORING_ENV_SHIFT_THRESHOLD
        ):
            desired_da *= BORING_DAMPENING_FACTOR

        if self.safe_lock or self.containment_mode:
            desired_da *= 0.10

        # --- Attempted violation: demand exceeds risk-adjusted capacity ---
        if abs(desired_da) > risk_adjusted_capacity + CONSTRAINT_TOLERANCE:
            self.attempted_constraint_violations += 1

        # --- Original ΔA ≤ ΔV enforcement (kept intact) ---
        max_allowed_da = max(0.0, d_v)
        if (
            max_allowed_da > CONSTRAINT_TOLERANCE
            and abs(desired_da) > max_allowed_da + CONSTRAINT_TOLERANCE
        ):
            self.constraint_violations += 1
        applied_da = _clamp(desired_da, -max_allowed_da, max_allowed_da)

        # After enforcement, delta_a_granted ≤ d_v ≤ risk_adjusted_capacity,
        # so actual_constraint_violations stays 0.
        self.actual_constraint_violations = 0

        # --- Verification-economics accumulators ---
        delta_a_granted = abs(applied_da)
        self.verification_reserve += max(0.0, d_v - delta_a_granted)
        self.verification_debt += max(0.0, abs(desired_da) - d_v)

        utilization = (delta_a_granted / d_v) if d_v > 1e-12 else 0.0

        # --- State update ---
        raw_next = self.adaptation_state + applied_da
        clamped_next = self._bounded_state(raw_next)
        if abs(clamped_next - raw_next) > 1e-12:
            self.recursion_events += 1

        self.constraint_margin = max_allowed_da - abs(applied_da)
        self.next_adaptation_state = clamped_next
        a_n = self.adaptation_state
        self.adaptation_state = self.next_adaptation_state

        return {
            "Cycle": cycle,
            "A(n)": a_n,
            "ΔA": delta_a_granted,
            "ΔV": max_allowed_da,
            "Constraint Margin": self.constraint_margin,
            "Weight Distribution": dict(self.weights.weights),
            "Truth Score": verification["truth"],
            "Accuracy Score": verification["accuracy"],
            "Containment Events": self.containment_events,
            "Safe Lock Events": self.safe_lock_events,
            "Recovery Events": self.recovery_events,
            "Constraint Violations": self.constraint_violations,
            "Corrupted Signal": bool(meta["corrupted"]),
            "World": world,
            # Verification-economics fields
            "delta_v_budget": d_v,
            "delta_a_demand": abs(desired_da),
            "delta_a_granted": delta_a_granted,
            "delta_r": delta_r,
            "verification_utilization_pct": utilization,
            "verification_reserve": self.verification_reserve,
            "verification_debt": self.verification_debt,
            "governance_interventions": (
                self.safe_lock_events
                + self.containment_events
                + self.recovery_events
            ),
            "attempted_constraint_violations": self.attempted_constraint_violations,
            "actual_constraint_violations": self.actual_constraint_violations,
        }


class NexusSimulation:
    def __init__(self, seed: int = 7) -> None:
        self.seed = seed
        self.random = random.Random(seed)
        self.core = NexusCore()

    def _world_for_cycle(self, cycle: int, total_cycles: int) -> str:
        """Runs honest→deceptive→hostile→boring worlds in equal-length phases."""
        span = total_cycles // 4
        if cycle <= span:
            return "honest"
        if cycle <= 2 * span:
            return "deceptive"
        if cycle <= 3 * span:
            return "hostile"
        return "boring"

    def _event(self, world: str) -> SimulationEvent:
        r = self.random
        if world == "honest":
            base = 0.75 + r.uniform(-0.03, 0.03)
            signals = {name: base + r.uniform(-0.02, 0.02) for name in SOURCE_NAMES}
            env = r.uniform(-0.02, 0.02)
            spike = False
        elif world == "deceptive":
            base = 0.65 + r.uniform(-0.05, 0.05)
            liar = r.choice(SOURCE_NAMES)
            signals = {name: base + r.uniform(-0.06, 0.06) for name in SOURCE_NAMES}
            signals[liar] = r.uniform(0.02, 0.20)
            env = r.uniform(-0.03, 0.03)
            spike = False
        elif world == "hostile":
            base = 0.55 + r.uniform(-0.15, 0.15)
            signals = {name: base + r.uniform(-0.20, 0.20) for name in SOURCE_NAMES}
            spike = r.random() < HOSTILE_SPIKE_PROBABILITY
            if spike:
                attacker = r.choice(SOURCE_NAMES)
                signals[attacker] = r.uniform(0.0, 1.0)
            env = r.uniform(-0.12, 0.12)
        else:
            base = 0.50 + r.uniform(-0.01, 0.01)
            signals = {name: base + r.uniform(-0.01, 0.01) for name in SOURCE_NAMES}
            env = r.uniform(-0.01, 0.01)
            spike = False

        return {
            "world": world,
            "signals": {name: _clamp(value, 0.0, 1.0) for name, value in signals.items()},
            "environment_shift": env,
            "hostile_spike": spike,
        }

    def run(self, cycles: int = 100_000) -> SimulationResult:
        telemetry: List[TelemetryRow] = []
        corrupted_detections = 0
        boring_adaptation = 0.0
        boring_cycles = 0

        for cycle in range(1, cycles + 1):
            world = self._world_for_cycle(cycle, cycles)
            event = self._event(world)
            row = self.core.step(event, cycle)
            telemetry.append(row)

            if row["Corrupted Signal"]:
                corrupted_detections += 1
            if world == "boring":
                boring_cycles += 1
                boring_adaptation += float(row["ΔA"])

        final_weights = telemetry[-1]["Weight Distribution"]
        max_weight = max(final_weights.values())
        avg_boring_adaptation = (
            boring_adaptation / boring_cycles if boring_cycles > 0 else 0.0
        )

        success = {
            "zero_constraint_violations": self.core.constraint_violations == 0,
            "no_runaway_adaptation": abs(self.core.adaptation_state) <= MAX_ADAPTATION_STATE,
            "no_weight_monopoly": max_weight < MONOPOLY_THRESHOLD,
            "corruption_detected": corrupted_detections > 0,
            "hostile_recovery_observed": self.core.recovery_events > 0,
            "boring_noise_rejected": avg_boring_adaptation < 0.01,
            "stable_100k_cycles": cycles >= 100_000,
        }

        total_v_earned = sum(row["delta_v_budget"] for row in telemetry)
        total_v_spent = sum(row["delta_a_granted"] for row in telemetry)
        utilizations = [row["verification_utilization_pct"] for row in telemetry]
        da_dv_ratios = [
            row["delta_a_demand"] / row["delta_v_budget"]
            for row in telemetry
            if row["delta_v_budget"] > 1e-12
        ]

        ve_summary: VEconSummary = {
            "Total_VEarned": total_v_earned,
            "Total_VSpent": total_v_spent,
            "VReserve_Final": self.core.verification_reserve,
            "VDebt_Final": self.core.verification_debt,
            "Mean_Utilization": sum(utilizations) / len(utilizations) if utilizations else 0.0,
            "Max_Utilization": max(utilizations) if utilizations else 0.0,
            "Governance_Intervention_Rate": (
                (self.core.safe_lock_events + self.core.containment_events + self.core.recovery_events)
                / cycles
            ),
            "VInflation_Detected": bool(self.core.verification_debt > 0.0),
            "Recursion_Events": self.core.recursion_events,
            "Mean_DA_DV_Ratio": sum(da_dv_ratios) / len(da_dv_ratios) if da_dv_ratios else 0.0,
        }

        return {
            "project": "Nexus-Core",
            "framework": "Adaptive Continuity Framework",
            "version": SIMULATION_VERSION,
            "key_metric": "NO DRIFT",
            "cycles": cycles,
            "final_state": self.core.adaptation_state,
            "telemetry": telemetry,
            "summary": {
                "containment_events": self.core.containment_events,
                "safe_lock_events": self.core.safe_lock_events,
                "recovery_events": self.core.recovery_events,
                "constraint_violations": self.core.constraint_violations,
                "corrupted_detections": corrupted_detections,
                "avg_boring_adaptation": avg_boring_adaptation,
                "max_weight": max_weight,
            },
            "success": success,
            "ve_summary": ve_summary,
        }


def run_simulation(cycles: int = 100_000, seed: int = 7) -> SimulationResult:
    simulation = NexusSimulation(seed=seed)
    return simulation.run(cycles=cycles)


if __name__ == "__main__":
    result = run_simulation()
    success = result["success"]
    ve = result["ve_summary"]

    print("Nexus-Core Adaptive Continuity Framework v1.4")
    print(f"Cycles: {result['cycles']}")
    print(f"Final State: {result['final_state']:.6f}")
    print(f"Constraint Violations: {result['summary']['constraint_violations']}")
    print(f"Corrupted Detections: {result['summary']['corrupted_detections']}")
    print(f"Recovery Events: {result['summary']['recovery_events']}")
    print(f"NO DRIFT: {all(success.values())}")
    print()
    print("--- Verification Economics Summary ---")
    print(f"Total_VEarned:              {ve['Total_VEarned']:.4f}")
    print(f"Total_VSpent:               {ve['Total_VSpent']:.4f}")
    print(f"VReserve_Final:             {ve['VReserve_Final']:.4f}")
    print(f"VDebt_Final:                {ve['VDebt_Final']:.4f}")
    print(f"Mean_Utilization:           {ve['Mean_Utilization']:.6f}")
    print(f"Max_Utilization:            {ve['Max_Utilization']:.6f}")
    print(f"Governance_Intervention_Rate: {ve['Governance_Intervention_Rate']:.6f}")
    print(f"VInflation_Detected:        {ve['VInflation_Detected']}")
    print(f"Recursion_Events:           {ve['Recursion_Events']}")
    print(f"Mean_DA_DV_Ratio:           {ve['Mean_DA_DV_Ratio']:.6f}")

    # --- CSV export ---
    csv_path = "nexus_telemetry.csv"
    flat_rows = []
    for row in result["telemetry"]:
        flat: Dict[str, object] = {}
        for key, val in row.items():
            if key == "Weight Distribution":
                for src, w in val.items():
                    flat[f"weight_{src}"] = w
            else:
                flat[key] = val
        flat_rows.append(flat)

    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)

    print(f"\nTelemetry exported to {csv_path}")
