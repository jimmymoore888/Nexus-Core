# Nexus-Core Copilot Governance Instructions

## Purpose

Use Nexus-Core as the governance framework for all Copilot work in this repository.
Nexus-Core is a **Distributed Verification Network research framework** — not a blockchain implementation.
Do not add blockchain infrastructure unless explicitly requested.

## Core Law

**ΔA ≤ ΔV** — the governing constraint must be preserved in all code changes.

- Never modify the governing law without explicit written approval.
- Every change must maintain:
  - `actual_constraint_violations = 0`
  - `final_verification_debt = 0`
  - All tests passing

## Feature Requirements

Every new feature must include:

- **Telemetry** — instrument the feature so its behavior is observable
- **Automated tests** — cover new code paths with unit or integration tests
- **Measurable reports** — generate report output when the feature produces measurable results

## Pre-PR Checklist

Before opening a pull request, always run the following commands and confirm they pass:

```bash
python nexus_simulation.py
python verification_report.py
python adversarial_simulations.py
python -m unittest discover -s tests -p "test_*.py"
```

## PR Summary Requirements

Every pull request description must include:

- **Files changed** — list of modified, added, or deleted files
- **Tests executed** — number and names of test cases run
- **Pass/fail status** — overall test result
- **`actual_constraint_violations`** — value from the simulation output
- **`final_verification_debt`** — value from the verification report
- **Reports generated** — list of report files produced

## Engineering Principles

- **Favor defensive validation over feature expansion.** Validate inputs and constraints before adding new capabilities.
- **Maintain verification economics.** Do not break the economic model governing verification incentives.
- **Maintain Safe Lock behavior.** Preserve the safe-lock mechanism that prevents constraint violations from propagating.
- **Treat Nexus-Core as a research framework.** Design decisions should prioritize correctness and verifiability over performance or feature breadth.
