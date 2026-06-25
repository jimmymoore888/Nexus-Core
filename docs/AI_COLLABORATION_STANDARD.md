# AI Collaboration Standard

## Purpose

Define how ChatGPT, Meta AI, GitHub Copilot, and any future AI assistant must collaborate on Nexus-Core.

## Core principle

Nexus-Core is governed by ΔA ≤ ΔV (Delta-A less than or equal to Delta-V).
Adaptation may only occur at the rate it can be verified.

In this standard, ΔA (Delta-A) means applied adaptation, ΔV (Delta-V) means available verification capacity, and ΔR (Delta-R) means the risk modifier used to bound adaptation.

Verification reserve, verification debt, and Safe Lock refer to the repository's existing telemetry and safety-control concepts.
SATDS refers to safety-critical adaptation and test decision surfaces, Napalm tests are adversarial stress tests for safety boundaries, and Byzantine consensus refers to multi-source disagreement handling.
Each of these governance concepts requires explicit review whenever a proposed change touches it.

## AI role separation

### 1. ChatGPT

- Architecture reasoning
- Systems design
- Review of doctrine, constraints, and roadmap
- Risk analysis before implementation

### 2. Meta AI

- Secondary review
- Alternative wording
- Cross-checking assumptions
- External perspective

### 3. GitHub Copilot

- Repository implementation
- Code generation
- Tests
- Reports
- Pull requests

### 4. Future AI agents

- Must follow the Nexus governing law
- Must preserve verification integrity
- Must not introduce unverified adaptation

## Required workflow for all AI-assisted work

1. Define the proposed change.
2. Identify whether it affects ΔA, ΔV, ΔR, verification reserve, verification debt, Safe Lock, SATDS, Napalm tests, or Byzantine consensus.
3. If it affects governance, require explicit review before implementation.
4. Implement only after the change is measurable through a defined telemetry, test, or report path.
5. Add or update telemetry.
6. Add or update tests.
7. Generate reports when applicable.
8. Run the validation suite.
9. Summarize results in the PR.

## Validation commands

```bash
python nexus_simulation.py
python verification_report.py
python adversarial_simulations.py
python -m unittest discover -s tests -p "test_*.py"
```

## Required PR summary

- AI tools involved
- Files changed
- Purpose of change
- Governance impact
- Tests run
- Pass/fail status
- actual_constraint_violations
- final_verification_debt
- reports generated
- whether ΔA ≤ ΔV remained intact

## Rules

- Do not modify the Nexus core law without explicit approval.
- Do not add blockchain infrastructure unless explicitly requested.
- Do not add features without telemetry.
- Do not add doctrine without measurement path.
- Do not treat AI output as truth without verification.
- All AI-generated work must be reviewable, testable, and reproducible.
