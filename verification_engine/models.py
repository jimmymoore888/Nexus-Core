"""
Data models for Nexus Verification Engine v0.1

Implements canonical response structures per NEXUS-CC-CON-001.
All snake_case naming convention.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum


class Decision(str, Enum):
    """Five authoritative verification decisions."""
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
class ValidationRecord:
    """Individual evidence validation in the lineage chain."""
    evidence_id: str
    timestamp: str  # ISO 8601
    status: ValidationStatus
    critical: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "critical": self.critical,
        }


@dataclass
class DecisionContext:
    """Decision reasoning and governing principle."""
    timestamp: str  # ISO 8601
    reasoning: str
    governing_principle: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "reasoning": self.reasoning,
            "governing_principle": self.governing_principle
        }


@dataclass
class CryptographicSignature:
    """Cryptographic signature over canonical response."""
    algorithm: str  # e.g., "SHA-256-DEMO-DIGEST"
    value: str     # hex-encoded signature
    key_id: str    # public key identifier
    timestamp: str # ISO 8601

    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "value": self.value,
            "key_id": self.key_id,
            "timestamp": self.timestamp
        }


@dataclass
class EvidenceLineage:
    """Complete evidence chain and decision history."""
    source: List[str]                          # evidence source identifiers
    validation: List[ValidationRecord]         # validation chain
    contribution: Dict[str, float]             # evidence contribution to risk
    decision: DecisionContext                  # decision context

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "validation": [v.to_dict() for v in self.validation],
            "contribution": self.contribution,
            "decision": self.decision.to_dict()
        }


@dataclass
class VerificationResponse:
    """
    Canonical flat response structure per NEXUS-CC-CON-001.
    All fields required for auditability and determinism.
    """
    decision: Decision
    requested_authority: str
    verified: bool
    validation_result: ValidationStatus
    validated_delta_a: float                   # ΔA: adaptation requested
    delta_v: float                             # ΔV: verification capacity
    risk_score: float                          # aggregated risk [0, 1]
    verification_margin: float                 # ΔV - ΔA
    mutation: bool                             # system mutation flag
    evidence_lineage: EvidenceLineage
    signature: CryptographicSignature

    def to_dict(self) -> Dict[str, Any]:
        """Convert to authoritative canonical representation."""
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

    def to_json(self) -> str:
        """Serialize to JSON with deterministic key ordering."""
        import json
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'))
