# Copilot Instructions

Use Nexus-Core as the governance framework for all Copilot work.

## Rules

1. Do not modify the Nexus core law: ΔA ≤ ΔV.
2. Any code change must preserve:
   - zero actual_constraint_violations
   - final_verification_debt = 0
   - tests passing
3. Any new feature must include:
   - telemetry
   - tests
   - report output if measurable
4. Copilot must not add blockchain infrastructure unless explicitly requested.
5. Copilot must treat Nexus-Core as a Distributed Verification Network research framework, not a blockchain implementation.
6. Before opening a PR, run:
   - python nexus_simulation.py
   - python verification_report.py
   - python adversarial_simulations.py
   - python -m unittest discover -s tests -p "test_*.py"
7. PR summaries must include:
   - files changed
   - tests executed
   - pass/fail status
   - actual_constraint_violations
   - final_verification_debt
   - reports generated
8. Favor defensive validation over feature expansion.
9. Maintain verification economics and Safe Lock behavior.

All Copilot work must also follow docs/AI_COLLABORATION_STANDARD.md.
