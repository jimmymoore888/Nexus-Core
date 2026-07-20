# Nexus Core (v1.4.0-beta.1)

Research framework for deterministic verification governed by **ΔA ≤ ΔV**.

- Engine version: **v0.1.1**
- Locked contract: `contracts/NEXUS-CC-CON-001.json`
- Locked-contract SHA-256: `7d96f7fcaea1f0677bc2fbac1e282e69b64942be7da40a91035aab61dc5f30bb`
- Historical `v1.3.0` is preserved in repository history.

## Scope implemented in this repository

- Python verification engine (`verification_engine/engine.py`)
- Node verification engine (`verification_engine/engine.js`)
- Local/mock HTTP service (`server.js`) with:
  - `POST /verify`
  - `POST /bridge/verify` (bounded in-memory TGLR demonstration)
- Simulations, adversarial checks, and unit/integration tests

This repository does **not** claim production TGLR federation, production Book Sentinel deployment, certification, paid pilot/customer deployment evidence, or independent external audit completion.

## Required test and verification commands

```bash
python run_tests.py
python -m unittest discover -s tests -q
npm test
python nexus_simulation.py
python verification_report.py
python adversarial_simulations.py
```

## Example request (`POST /verify`)

`evaluation_timestamp` is required.

```json
{
  "target_id": "system_001",
  "requested_authority": "ANALYZE",
  "requested_delta_a": 0.31,
  "evaluation_timestamp": "2026-07-20T00:00:00Z",
  "evidence_items": [
    {
      "evidence_id": "EVD-001",
      "source": "runtime_telemetry",
      "timestamp": "2026-07-19T23:59:59Z",
      "data": {
        "verification_status": "valid",
        "confidence": 0.95
      }
    }
  ]
}
```

## Signature field compatibility note

The contract field name `signature` is locked for compatibility.
Current implementation uses `algorithm: "SHA-256-DEMO-DIGEST"` as a deterministic demonstration digest label.
It is not presented as a production digital-signature/certification claim.

## Governance boundary

The frozen Constitution v0.2 source-of-truth has not yet been recovered in this repository.
Do not reconstruct Constitution text from implementation artifacts.
See:
- `docs/governance/CONSTITUTION-V02-RECOVERY-GAP.md`
- `docs/governance/GOVERNANCE-SOURCE-OF-TRUTH-STATUS.md`
