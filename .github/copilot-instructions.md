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

---

## Constitutional Source-of-Truth Control

### Frozen Baseline

The project owner, Jimmy W. Moore, has designated:

`NEXUS-CONST-v0.2-FROZEN-2026-07-16`

as the frozen Nexus Core constitutional baseline.

The complete authoritative article-by-article text has not yet been
verified as present inside this repository.

Until that source-of-truth document is recovered and approved:

1. Do not create, reconstruct, summarize, replace, or silently edit
   Constitution v0.2.
2. Do not infer constitutional wording from README files, contracts,
   diagrams, tests, source code, issues, pull requests, or implementation.
3. Do not assign constitutional article numbers to proposed concepts.
4. Do not claim that a proposal, specification, diagram, or implementation
   has constitutional authority.
5. State missing evidence and uncertainty directly. Do not guess.
6. Preserve all previous versions and complete change history.
7. Do not merge any pull request without explicit approval from
   Jimmy W. Moore.

### Required Development Order

Constitution
→ Formal Specification
→ Executable Controls
→ Verification Evidence

Implementation follows the Constitution.
The Constitution does not drift with implementation.

### Proposed Conscience and Library Architecture

The following concepts are proposed architecture and are not yet
authorized for executable implementation:

- The Book — Living Conscience
- The Book Sentinel
- The Great Library — Collective Memory
- secure inter-Book experience exchange
- distributed knowledge admission
- Library checkpoint or consensus mechanisms
- automated inherited knowledge
- Library-to-actuator pathways

No code, schema, service, cryptographic protocol, consensus mechanism,
or automated knowledge-exchange system for these concepts may be
created until controlled constitutional and specification documents
are approved.

### Knowledge Independence Rules

- Knowledge shared is not knowledge automatically believed.
- Shared experience is not shared identity.
- Consensus is not truth.
- A signature proves integrity and key control; it does not prove that
  narrative content is true.
- Imported knowledge is not locally verified knowledge.
- No external Book may write directly into another Book.
- No Library contribution may directly command an actuator.
- Imported adaptation remains governed by:

  ΔA_import ≤ ΔV_receiver

### Non-Revision Rule

Corrections must append to history rather than silently replacing it.

Missing constitutional text shall never be replaced by assumption.
