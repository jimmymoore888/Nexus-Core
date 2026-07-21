# Internal Verification Report

This report is internal repository evidence only.

## Command Results

- `python run_tests.py` → success (`Ran 87 tests`, `Failures: 0`, `Errors: 0`)
- `python -m unittest discover -s tests -q` → success (`Ran 87 tests`, `OK`)
- `npm test` → success:
  - fixtures: `39/39`
  - server: `5/5`
  - bridge: `8/8`
  - bridge server: `5/5`
  - seeded invariants: `10 assertion groups`, `actual_constraint_violations = 0`
- `python nexus_simulation.py` → success (`Constraint Violations: 0`, `VDebt_Final: 0.0000`, `Cycles: 100000`)
- `python verification_report.py` → success (`actual_constraint_violations: 0`, `final_verification_debt: 0.0`)
- `python adversarial_simulations.py` → success
- `python scripts/check_versions.py` → success
- `python scripts/check_locked_contract.py` → success
- `python scripts/check_claims.py` → success
- `npm audit --omit=dev` → success (`0 vulnerabilities`)

## Distinctions

- Internal verification evidence: this report and local command outputs.
- CI evidence: produced by GitHub Actions runs.
- Bounded bridge demonstration evidence: local in-memory bridge tests/spec/demo.
- External review/certification/production/customer/paid-pilot evidence: not claimed in this report.

## Core outputs

- `actual_constraint_violations = 0`
- `final_verification_debt = 0.0`
- `locked_contract_sha256 = 7d96f7fcaea1f0677bc2fbac1e282e69b64942be7da40a91035aab61dc5f30bb`
