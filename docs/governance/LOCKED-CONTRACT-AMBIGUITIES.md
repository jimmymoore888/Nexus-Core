# Locked Contract Ambiguities (Recorded, Not Resolved)

This document records known ambiguities without modifying `contracts/NEXUS-CC-CON-001.json`.

1. `signature` field name is contract-locked, while implementation currently uses deterministic `SHA-256-DEMO-DIGEST` compatibility labeling.
2. `THROTTLE` and `REVERSE` are present in enum space but not currently emitted by implemented decision logic.
3. `mutation` remains contract-required but is not derived from runtime state mutation in this repository.
4. Evidence failure behavior (collapse vs exclusion/recalculation) must remain explicit per implementation evidence.
5. Criticality semantics are implementation-defined pending constitutional/spec clarification.
6. `INVALID` may appear in top-level `validation_result`, while lineage validation entries remain constrained to `VALID|EXPIRED|UNVERIFIED`.
7. Constitution v0.2 source-of-truth text is still missing from repository evidence.
8. Bridge metadata/contract boundaries are additive and non-authoritative relative to the locked engine contract.
