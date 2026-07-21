# TGLR End-to-End Bridge Specification (Bounded Demo)

- **Document ID:** TGLR-END-TO-END-BRIDGE-001
- **Revision:** 0.1
- **Status:** BOUNDED DEMONSTRATION SPECIFICATION

This specification defines a local, in-memory demonstration bridge from front-end envelope requests to the existing locked verification engine response.

## Flow

1. Front-end submits `/bridge/verify` request envelope.
2. Bridge performs strict pre-validation.
3. Bridge enforces Book/Sentinel boundary controls.
4. Bridge invokes the existing verification engine.
5. Bridge records bounded in-memory audit metadata.
6. Bridge admits state only on `GRANT`.
7. Bridge returns bridge metadata + unrenamed engine response payload.

## Required controls

- Duplicate `request_id` and duplicate `state_id` rejection.
- Unauthorized cross-Book rejection.
- Direct-memory-write request rejection.
- Parent-state existence checks (reject orphan/nonexistent parent states).
- Engine invocation before any admission action.
- Admission only when engine `decision == GRANT`.
- No admission after `REJECT` or `SAFE_LOCK`.
- Rejected attempts retained in separate audit trail entries.
- Deterministic explicit timestamps required from caller.
- In-memory bounded scope only (no DB, blockchain, token, actuator path).

## Explicit limitations

- Demonstration metadata does not grant data access.
- Connectivity metadata does not imply trust or authority transfer.
- Finite tests and finite growth/connectivity proxies do not prove the UIR infinite axiom.
