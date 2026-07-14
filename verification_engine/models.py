"""
Canonical response models for Nexus Verification Engine v0.1
Implements NEXUS-CC-CON-001 contract
"""

from enum import Enum
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime


class Decision(str, Enum):
    """Five authoritative decisions."""
    GRANT = "GRANT"
    THROTTLE = "THROTTLE"
    REJECT = "REJECT"
    REVERSE = "REVERSE"
    SAFE_LOCK = "SAFE_LOCK"


class ValidationStatus(str, Enum):
    """Evidence validation status."""
    VALID = "VALID"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class ValidationEntry:
    """Entry in evidence validation chain."""
    evidence_id: str
    timestamp: str
    status: str

    def to_dict(self):
        return asdict(self)


@dataclass
class DecisionContext:
    """Decision reasoning and context."""
    timestamp: str
    reasoning: str
    governing_principle: str

    def to_dict(self):
        return asdict(self)


@dataclass
class EvidenceLineage:
    """Complete evidence lineage for auditability."""
    source: List[str]
    validation: List[Dict]
    contribution: Dict[str, float]
    decision: Dict

    def to_dict(self):
        return {
            "source": self.source,
            "validation": self.validation,
            "contribution": self.contribution,
            "decision": self.decision
        }


@dataclass
class Signature:
    """Cryptographic signature."""
    algorithm: str
    value: str
    key_id: str
    timestamp: str

    def to_dict(self):
        return asdict(self)


@dataclass
class VerificationResponse:
    """Canonical verification response implementing NEXUS-CC-CON-001."""
    
    decision: Decision
    requested_authority: str
    verified: bool
    validation_result: ValidationStatus
    validated_delta_a: float
    delta_v: float
    risk_score: float
    verification_margin: float
    mutation: bool
    evidence_lineage: EvidenceLineage
    signature: Signature

    def to_dict(self):
        return {
            "decision": self.decision.value,
            "requested_authority": self.requested_authority,
            "verified": self.verified,
            "validation_result": self.validation_result.value,
            "validated_delta_a": self.validated_delta_a,
            "delta_v": self.delta_v,
            "risk_score": self.risk_score,
            "verification_margin": self.verification_margin,
            "mutation": self.mutation,
            "evidence_lineage": self.evidence_lineage.to_dict(),
            "signature": self.signature.to_dict()
        }

    def to_json(self):
        import json
        return json.dumps(self.to_dict(), indent=2)
