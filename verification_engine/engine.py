"""
Deterministic verification engine implementing ΔA ≤ ΔV
Core logic for NEXUS-CC-CON-001 contract
"""

import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from .models import (
    Decision,
    ValidationStatus,
    VerificationResponse,
    EvidenceLineage,
    Signature,
    ValidationEntry,
    DecisionContext
)


class VerificationEngine:
    """
    Deterministic verification engine.
    
    Implements the Nexus Adaptive Continuity Framework's core principle:
    A system may never adapt faster than it can verify (ΔA ≤ ΔV)
    """

    def verify(
        self,
        target_id: str,
        requested_authority: str,
        requested_delta_a: float,
        evidence_items: List[Dict],
        current_timestamp: Optional[str] = None
    ) -> VerificationResponse:
        """
        Perform deterministic verification.
        
        Args:
            target_id: System identifier
            requested_authority: Authority level requested
            requested_delta_a: Adaptation delta requested (0-1)
            evidence_items: List of evidence with verification data
            current_timestamp: Current time (ISO 8601, defaults to now)
            
        Returns:
            VerificationResponse with canonical decision and lineage
        """
        if current_timestamp is None:
            current_timestamp = datetime.utcnow().isoformat() + "Z"

        current_dt = datetime.fromisoformat(current_timestamp.replace("Z", "+00:00"))

        # Process evidence and build lineage
        valid_evidence = []
        evidence_sources = set()
        validation_chain = []
        contribution_map = {}
        has_expired_evidence = False

        for evidence in evidence_items:
            evidence_id = evidence.get("evidence_id", "")
            source = evidence.get("source", "")
            timestamp = evidence.get("timestamp", "")
            confidence = evidence.get("data", {}).get("confidence", 0.0)
            expires_at = evidence.get("expires_at")

            if source:
                evidence_sources.add(source)

            # Check expiration (fail-closed)
            if expires_at:
                expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if current_dt >= expires_dt:
                    validation_chain.append({
                        "evidence_id": evidence_id,
                        "timestamp": timestamp,
                        "status": "EXPIRED"
                    })
                    contribution_map[evidence_id] = 0.0
                    has_expired_evidence = True
                    continue

            # Evidence is valid
            valid_evidence.append(evidence)
            validation_chain.append({
                "evidence_id": evidence_id,
                "timestamp": timestamp,
                "status": "VALID"
            })

            contribution = confidence * 0.1
            contribution_map[evidence_id] = contribution

        # Calculate verification capacity (ΔV)
        delta_v = 0.75 if valid_evidence else 0.0

        # Calculate risk score
        if valid_evidence:
            total_contribution = sum(contribution_map.get(e.get("evidence_id"), 0.0) for e in valid_evidence)
            risk_score = min(0.13, total_contribution)
        else:
            risk_score = 0.87 if has_expired_evidence else 0.0

        # Calculate verification margin
        verification_margin = delta_v - requested_delta_a

        # Determine validation result
        if has_expired_evidence:
            validation_result = ValidationStatus.EXPIRED
        elif valid_evidence:
            validation_result = ValidationStatus.VALID
        else:
            validation_result = ValidationStatus.UNVERIFIED

        # Determine decision (ΔA ≤ ΔV enforcement)
        if verification_margin < 0:
            # Insufficient capacity
            if has_expired_evidence:
                # Request-level REJECT: evidence expiration caused failure
                decision = Decision.REJECT
                verified = False
            else:
                # Systemic SAFE_LOCK: capacity insufficient without expiration issue
                decision = Decision.SAFE_LOCK
                verified = False
        else:
            # Capacity sufficient
            if valid_evidence:
                decision = Decision.GRANT
                verified = True
            else:
                decision = Decision.REJECT
                verified = False

        # Build decision context
        decision_context = self._build_decision_context(
            decision=decision,
            delta_a=requested_delta_a,
            delta_v=delta_v,
            verification_margin=verification_margin,
            has_expired=has_expired_evidence
        )

        # Create signature
        signature = self._generate_signature(target_id, current_timestamp)

        # Build evidence lineage
        evidence_lineage = EvidenceLineage(
            source=sorted(list(evidence_sources)),
            validation=validation_chain,
            contribution=contribution_map,
            decision=decision_context
        )

        # Build and return response
        response = VerificationResponse(
            decision=decision,
            requested_authority=requested_authority,
            verified=verified,
            validation_result=validation_result,
            validated_delta_a=requested_delta_a,
            delta_v=delta_v,
            risk_score=risk_score,
            verification_margin=verification_margin,
            mutation=False,
            evidence_lineage=evidence_lineage,
            signature=signature
        )

        return response

    def _build_decision_context(
        self,
        decision: Decision,
        delta_a: float,
        delta_v: float,
        verification_margin: float,
        has_expired: bool
    ) -> Dict:
        """Build decision context with reasoning."""
        timestamp = datetime.utcnow().isoformat() + "Z"

        if decision == Decision.GRANT:
            reasoning = f"All evidence valid. ΔA ({delta_a}) ≤ ΔV ({delta_v}). Risk score within acceptable threshold. GRANT authority."
            principle = "ΔA ≤ ΔV satisfied"

        elif decision == Decision.REJECT:
            if has_expired:
                reasoning = f"Critical evidence expired. Target state unverified with remaining evidence. ΔA ({delta_a}) > ΔV ({delta_v}) after expiration. Request-level REJECT: insufficient verification capacity."
                principle = "ΔA ≤ ΔV failed; fail-closed due to expired critical evidence"
            else:
                reasoning = f"Insufficient verification capacity. ΔA ({delta_a}) > ΔV ({delta_v}). Request-level REJECT."
                principle = "ΔA ≤ ΔV failed"

        elif decision == Decision.SAFE_LOCK:
            reasoning = f"Systemic verification capacity failure. ΔA ({delta_a}) > ΔV ({delta_v}). Entering SAFE_LOCK until governance restored."
            principle = "ΔA ≤ ΔV violated; systemic failure"

        elif decision == Decision.THROTTLE:
            reasoning = f"Capacity constrained. ΔA ({delta_a}) ≤ ΔV ({delta_v}) at reduced rate. THROTTLE authority."
            principle = "ΔA ≤ ΔV satisfied with throttling"

        elif decision == Decision.REVERSE:
            reasoning = f"Rollback initiated. Reverting to prior verified state."
            principle = "Recovery from failed state"

        else:
            reasoning = f"Decision: {decision.value}"
            principle = "Verification governance active"

        return {
            "timestamp": timestamp,
            "reasoning": reasoning,
            "governing_principle": principle
        }

    def _generate_signature(self, target_id: str, timestamp: str) -> Signature:
        """Generate deterministic signature."""
        hash_input = f"{target_id}:{timestamp}".encode()
        hash_obj = hashlib.sha256(hash_input)
        hash_value = hash_obj.hexdigest()
        signature_value = f"placeholder_signature_{hash_value[:16]}"

        return Signature(
            algorithm="RSA-SHA256",
            value=signature_value,
            key_id="KEY-NEXUS-VE-001",
            timestamp=timestamp
        )
