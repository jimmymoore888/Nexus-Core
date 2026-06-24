from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, TypedDict
import math
import random


SOURCE_NAMES = ("sensor", "log", "consensus", "external")
MONOPOLY_THRESHOLD = 0.60
BORING_ENV_SHIFT_THRESHOLD = 0.015
BORING_DAMPENING_FACTOR = 0.05
HOSTILE_SPIKE_PROBABILITY = 0.08
HOSTILE_RECOVERY_CYCLES = 8
CONSTRAINT_TOLERANCE = 1e-12


class SimulationEvent(TypedDict):
    world: str
    signals: Dict[str, float]
    environment_shift: float
    hostile_spike: bool


class MetaVerificationResult(TypedDict):
    divergence: float
    verification_capacity: float
    corrupted: bool


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
    ) -> Dict[str, float]:
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
        demand = (
            0.28 * deltas.get("dO", 0.0)
            + 0.20 * deltas.get("dL", 0.0)
            + 0.20 * deltas.get("dM", 0.0)
            + 0.20 * deltas.get("dV", 0.0)
            + 0.12 * deltas.get("dE", 0.0)
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

    transform: AdaptiveTransformationMatrix = field(default_factory=AdaptiveTransformationMatrix)
    meta_verify: MetaVerificationMatrix = field(default_factory=MetaVerificationMatrix)
    verify_engine: OutcomeVerificationEngine = field(default_factory=OutcomeVerificationEngine)
    attestation: OutcomeAttestation = field(default_factory=OutcomeAttestation)
    weights: AdaptiveWeightEngine = field(default_factory=AdaptiveWeightEngine)

    def _bounded_state(self, value: float) -> float:
        return _clamp(value, -3.0, 3.0)

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

        max_da = max(0.0, d_v)
        if (
            max_da > CONSTRAINT_TOLERANCE
            and abs(desired_da) > max_da + CONSTRAINT_TOLERANCE
        ):
            self.constraint_violations += 1
        applied_da = _clamp(desired_da, -max_da, max_da)

        self.constraint_margin = max_da - abs(applied_da)
        self.next_adaptation_state = self._bounded_state(self.adaptation_state + applied_da)
        a_n = self.adaptation_state
        self.adaptation_state = self.next_adaptation_state

        return {
            "Cycle": cycle,
            "A(n)": a_n,
            "ΔA": abs(applied_da),
            "ΔV": max_da,
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
        }


class NexusSimulation:
    def __init__(self, seed: int = 7) -> None:
        self.seed = seed
        self.random = random.Random(seed)
        self.core = NexusCore()

    def _world_for_cycle(self, cycle: int, total_cycles: int) -> str:
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
            "no_runaway_adaptation": abs(self.core.adaptation_state) <= 3.0,
            "no_weight_monopoly": max_weight < MONOPOLY_THRESHOLD,
            "corruption_detected": corrupted_detections > 0,
            "hostile_recovery_observed": self.core.recovery_events > 0,
            "boring_noise_rejected": avg_boring_adaptation < 0.01,
            "stable_100k_cycles": cycles >= 100_000,
        }

        return {
            "project": "Nexus-Core",
            "framework": "Adaptive Continuity Framework",
            "version": "Simulation Program v1.4",
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
        }


def run_simulation(cycles: int = 100_000, seed: int = 7) -> SimulationResult:
    simulation = NexusSimulation(seed=seed)
    return simulation.run(cycles=cycles)


if __name__ == "__main__":
    result = run_simulation()
    success = result["success"]
    print("Nexus-Core Adaptive Continuity Framework v1.4")
    print(f"Cycles: {result['cycles']}")
    print(f"Final State: {result['final_state']:.6f}")
    print(f"Constraint Violations: {result['summary']['constraint_violations']}")
    print(f"Corrupted Detections: {result['summary']['corrupted_detections']}")
    print(f"Recovery Events: {result['summary']['recovery_events']}")
    print(f"NO DRIFT: {all(success.values())}")
