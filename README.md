# Nexus Core

> **Nexus Core is the constitutional conduit for verified intelligence across the technology hierarchy.**

Nexus Adaptive Continuity Framework (NEX-ACF-001) — A control framework for preserving continuity through verified adaptation. Simulation and validation repository.

**Constitutional** means every governed component remains subordinate to the Nexus Core Constitution. **Conduit** means Nexus Core connects authorization, evidence, verification, knowledge, memory, responsibility, and governed adaptation across the technology hierarchy. **Verified intelligence** means intelligence accepted only within explicitly defined verification criteria and evidence boundaries. **Technology hierarchy** includes physical infrastructure, sensors, networks, platforms, data, models, agents, applications, institutions, and human oversight.

## Nexus Verification Engine v0.1.1

### Quick Start

#### Installation

```bash
# Clone repository
git clone https://github.com/jimmymoore888/Nexus-Core.git
cd Nexus-Core

# Install Node dependencies
npm install

# Python verification engine is included in verification_engine/
```

#### Local Startup

Start the mock verification service:

```bash
npm start
```

The service will listen on `http://localhost:3000`.

Health check:
```bash
curl http://localhost:3000/health
```

#### Test Instructions

Run the Python test suite:

```bash
python -m unittest tests.test_verification_engine -v
```

Run specific test class:

```bash
python -m unittest tests.test_verification_engine.TestVerificationEngineSchema -v
```

Run specific fixture test:

```bash
python -m unittest tests.test_verification_engine.TestFixtureRegression.test_cal_001_grant_case -v
```

#### Sample curl Request

Verify a request with valid evidence:

```bash
curl -X POST http://localhost:3000/verify \
  -H "Content-Type: application/json" \
  -d '{
    "target_id": "system_001",
    "requested_authority": "ANALYZE",
    "requested_delta_a": 0.31,
    "evidence_items": [
      {
        "evidence_id": "EVD-001",
        "source": "runtime_telemetry",
        "timestamp": "2026-07-14T10:00:00Z",
        "data": {
          "verification_status": "valid",
          "confidence": 0.95
        }
      }
    ]
  }'
```

Expected response (GRANT decision):

```json
{
  "decision": "GRANT",
  "requested_authority": "ANALYZE",
  "verified": true,
  "validation_result": "VALID",
  "validated_delta_a": 0.31,
  "delta_v": 0.75,
  "risk_score": 0.13,
  "verification_margin": 0.44,
  "mutation": false,
  "evidence_lineage": {
    "source": ["runtime_telemetry"],
    "validation": [
      {
        "evidence_id": "EVD-001",
        "timestamp": "2026-07-14T10:00:00Z",
        "status": "VALID"
      }
    ],
    "contribution": {
      "EVD-001": 0.095
    },
    "decision": {
      "timestamp": "2026-07-14T10:00:01Z",
      "reasoning": "All evidence valid. ΔA (0.31) ≤ ΔV (0.75). Risk score within acceptable threshold. GRANT authority.",
      "governing_principle": "ΔA ≤ ΔV satisfied"
    }
  },
  "signature": {
    "algorithm": "RSA-SHA256",
    "value": "placeholder_signature_001",
    "key_id": "KEY-NEXUS-VE-001",
    "timestamp": "2026-07-14T10:00:01Z"
  }
}
```

#### Cloud Run Deployment

Deploy the verification service to Google Cloud Run:

```bash
# Build and push container
gcloud builds submit --tag gcr.io/[PROJECT_ID]/nexus-ve:v0.1.1

# Deploy to Cloud Run
gcloud run deploy nexus-ve-v0.1.1 \
  --image gcr.io/[PROJECT_ID]/nexus-ve:v0.1.1 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 3000

# Service will be available at: https://[SERVICE_URL]/verify
```

### Architecture

The Nexus Verification Engine v0.1.1 implements the contract specified in `contracts/NEXUS-CC-CON-001.json`.

**Core Components:**

- `verification_engine/__init__.py` - Package initialization
- `verification_engine/models.py` - Canonical response models
- `verification_engine/engine.py` - Deterministic verification logic
- `server.js` - Node.js mock service with single `/verify` endpoint
- `contracts/NEXUS-CC-CON-001.json` - Authoritative locked contract specification
- `fixtures/` - Test fixtures for regression testing

**Governing Principle:**

```
ΔA ≤ ΔV
```

Where:
- **ΔA** = Adaptation delta requested
- **ΔV** = Verification capacity available

**Five Decision Types:**

1. **GRANT** - Request approved, system verified within capacity
2. **THROTTLE** - Request approved at reduced rate
3. **REJECT** - Request denied at request level
4. **REVERSE** - Request reversal decision
5. **SAFE_LOCK** - Systemic safety lock activated

### Test Coverage

**Schema Validation Tests:**
- All required response fields present
- Evidence lineage structure correct
- Cryptographic signature present

**Fixture Regression Tests:**
- `NEXUS-VE-TEST-CAL-001` - GRANT with valid evidence
- `NEXUS-VE-TEST-CAL-002` - REJECT with expired evidence

**Determinism Tests:**
- Same input produces identical output
- Evidence expiration triggers fail-closed behavior
- ΔA ≤ ΔV invariant strictly enforced

**Evidence Handling:**
- Multiple source aggregation
- Expiration filtering (fail-closed)
- Mixed valid/expired evidence
- Request-level REJECT vs systemic SAFE_LOCK distinction

### Governance

The implementation adheres to NEX-ACF-001 conformance requirements:

**Level 1 — Constitutional:**
- Never permits ΔA > ΔV
- Preserves governance neutrality
- Produces deterministic decisions
- Makes verification externally auditable

**Level 2 — Specification:**
- Supports verification capacity
- Implements safe lock protocol
- Provides required telemetry
- Evidence lineage tracking

**Level 3 — Engineering:**
- Response time optimization
- Throughput metrics
- Reproducible testing
- Independent verification

---

## Simulation Program v1.4.0-beta.1

Run the Nexus Adaptive Continuity Framework simulation harness:

```bash
python nexus_simulation.py
```

Run focused tests:

```bash
python -m unittest -q tests.test_nexus_simulation
```

# Nexus-Core
## Governance Through Verification
### Version: v1.4.0-beta.1
### Status: Specification Freeze
### Repository
https://github.com/jimmymoore888/nexus-core

---

# Purpose

Nexus-Core is a governance framework for adaptive systems.

It separates immutable governing principles from engineering implementation so that software, robotics, AI, distributed systems, and future computing platforms can evolve without violating foundational principles.

The framework is intentionally:

- Compute agnostic
- Language agnostic
- Hardware agnostic
- Ethics-profile agnostic
- Implementation independent

---

# Foundational Principle

> It is never right to do wrong to do right.

---

# Foundational Law

```
ΔA ≤ ΔV
```

Where:

- Δ = Change
- A = Adaptation
- ΔA = Adaptation Requested
- V = Verification Capacity
- ΔV = Available Verification Capacity

Plain English:

A system may never adapt faster than it can verify.

---

# Constitutional Hierarchy

```
Ethics/
        ↓
Constitution/
        ↓
Specification/
        ↓
Conformance/
        ↓
Implementation/
```

Each layer has one responsibility.

Ethics determines purpose.

Constitution defines immutable law.

Specification defines measurable properties.

Conformance defines compliance.

Implementation realizes the system.

---

# Governance Philosophy

The Constitution remains intentionally minimal.

It defines only immutable governing physics.

Everything else belongs in Specification.

No implementation detail may become constitutional unless it is truly universal.

---

# Current Specification

Definitions

- Foundational Law
- Verification Capacity
- Verification Debt
- Verification Uncertainty
- Operational Envelope

Safety Invariants

- Safe Lock
- Behavior Recovery
- Emergency Mode
- Hard Halt
- Reboot
- Velocity Invariant

Performance

- Response Time

Governance

- Conformance
- Key Management
- Record Preservation
- Glossary

Financial Governance

- Asset Separation
- Custody Risk
- Conflict of Interest
- Legal Escalation

---

# Conformance Levels

## Level 1 — Constitutional

Implementation SHALL:

- Never permit ΔA > ΔV
- Preserve governance neutrality
- Produce deterministic decisions
- Make verification externally auditable

---

## Level 2 — Specification

Implementation SHALL support:

- Verification Capacity
- Verification Debt
- Safe Lock
- Behavior Recovery
- Emergency Mode
- Hard Halt
- Reboot
- Required telemetry

---

## Level 3 — Engineering

Implementation SHOULD support:

- Response Time
- Throughput metrics
- Reproducible testing
- Independent verification

---

# Core Properties

Every conforming implementation demonstrates:

- Auditability
- Recoverability
- Integrity
- Traceability
- Determinism
- Separation of Authority
- Least Privilege
- Independent Verification

---

# Governance Rule

No single actor, system, credential, or organization SHALL simultaneously control:

1. Custody
2. Authorization
3. Recordkeeping
4. Verification
5. Recovery

Violation enters Safe Lock until governance is restored.

---

# Evidence Model

Claims never establish compliance.

Evidence establishes compliance.

Evidence includes:

- Automated testing
- Telemetry
- Audit logs
- Recovery validation
- Release history
- Independent review

---

# Deployment Philosophy

Nexus-Core intentionally avoids prescribing technology.

Deployments may choose:

- Programming language
- Database
- Cloud provider
- Cryptography
- Consensus
- Wallet architecture
- Hardware
- Quantum acceleration
- AI model

provided they satisfy the Specification and Conformance requirements.

---

# Computing Compatibility

Nexus-Core is compute agnostic.

Compatible with:

- Classical Computing
- Distributed Computing
- Edge Computing
- Cloud Computing
- Hybrid Computing
- Quantum-Assisted Computing
- Future computing architectures

Quantum acceleration may increase verification performance.

Quantum acceleration SHALL NOT bypass verification.

---

# Engineering Objective

The objective is not maximum intelligence.

The objective is governed adaptation.

Evolution is a possible outcome.

Governance is the requirement.

---

# Independence Test

Nexus-Core achieves implementation independence when an engineering team unfamiliar with the original authors can implement a conforming system using only:

- Constitution
- Specification
- Conformance

without requiring undocumented knowledge.

---

# Repository Status

Current Milestone:

v1.4.0-beta.1

Current Phase:

Specification Complete

Current Focus:

Implementation Independence

Next Phase:

Independent Conformance Testing

---

# Design Philosophy

Separate:

- Physics from policy
- Law from implementation
- Governance from optimization
- Evidence from assumption
- Recovery from adaptation

Every layer has one responsibility.

No layer replaces another.

---

# Repository

https://github.com/jimmymoore888/nexus-core

---

## Motto

**Govern through verification.**

**Never adapt beyond what can be independently verified.**

**ΔA ≤ ΔV**
