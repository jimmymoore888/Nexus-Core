"""
Nexus Verification Engine v0.1

A deterministic verification system implementing NEXUS-CC-CON-001.
Governed by: ΔA ≤ ΔV
"""

__version__ = "0.1.0"
__contract__ = "NEXUS-CC-CON-001"

from verification_engine.engine import VerificationEngine
from verification_engine.models import VerificationResponse, EvidenceLineage

__all__ = [
    "VerificationEngine",
    "VerificationResponse",
    "EvidenceLineage",
]
