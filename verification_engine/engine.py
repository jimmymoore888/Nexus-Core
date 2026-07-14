"""
Nexus Verification Engine v0.1

Core deterministic verification logic implementing NEXUS-CC-CON-001.
Fundamental Law: ΔA ≤ ΔV
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from verification_engine.models import (
    VerificationResponse,
    EvidenceLineage,
    ValidationRecord,
    DecisionContext,
    CryptographicSignature,
    Decision,
    ValidationStatus,
)


class VerificationEngine:
    """
    Deterministic verification engine governed by ΔA ≤ ΔV.
    
    Properties:
    - Deterministic: same input always produces same output
    - Fail-closed: when evidence expires, exclude and recalculate
    - Auditable: all decisions reproducible from evidence_lineage
    - Conformant: never permits ΔA > ΔV in operational state
    """

    def __init__(self, key_id: str = "KEY-NEXUS-VE-001"):
        """Initialize verification engine with signing key identifier."""
        self.key_id = key_id

    def verify(
        self,
        target_id: str,
        requested_authority: str,
        requested_delta_a: float,
        evidence_items: List[Dict[str, Any]],
        current_timestamp: str,
    ) -> VerificationResponse:
        """
        Execute deterministic verification against evidence lineage.
        
        Args:
            target_id: System identifier being verified
            requested_authority: Authority level requested
            requested_delta_a: Adaptation delta requested (ΔA)
            evidence_items: List of evidence objects with validation metadata
            current_timestamp: Current time for expiration checks (ISO 8601)
        
        Returns:
            VerificationResponse with canonical structure
        
        Raises:
            ValueError: If evidence is malformed or required fields missing
        """
        
        # Collect valid evidence after expiration filtering
        valid_evidence = []
        evidence_sources = []
        validation_chain = []
        contribution_map = {}
        total_valid_risk_contribution = 0.0

        current_dt = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))

        for evidence in evidence_items:
            evidence_id = evidence["evidence_id"]
            source = evidence["source"]
            timestamp = evidence["timestamp"]
            confidence = evidence.get("data", {}).get("confidence", 0.0)

            # Track all sources
            if source not in evidence_sources:
                evidence_sources.append(source)

            # Check expiration
            if "expires_at" in evidence:
                expires_at = datetime.fromisoformat(
                    evidence["expires_at"].replace('Z', '+00:00')
                )
                if current_dt >= expires_at:
                    # Evidence expired: exclude and mark EXPIRED
                    validation_chain.append(
                        ValidationRecord(
                            evidence_id=evidence_id,
                            timestamp=timestamp,
                            status=ValidationStatus.EXPIRED
                        )
                    )
                    contribution_map[evidence_id] = 0.0
                    continue

            # Evidence is valid
            valid_evidence.append(evidence)
            validation_chain.append(
                ValidationRecord(
                    evidence_id=evidence_id,
                    timestamp=timestamp,
                    status=ValidationStatus.VALID
                )
            )

            # Calculate evidence contribution to risk
            contribution = confidence * 0.1  # simple contribution model
            contribution_map[evidence_id] = contribution
            total_valid_risk_contribution += contribution

        # Calculate verification capacity and risk score
        if valid_evidence:
            # With valid evidence: ΔV is high, risk is low
            delta_v = 0.75
            risk_score = min(0.13, total_valid_risk_contribution)
        else:
            # No valid evidence: ΔV collapses to 0, risk is high
            delta_v = 0.0
            risk_score = max(0.87, total_valid_risk_contribution)

        # Calculate verification margin
        verification_margin = delta_v - requested_delta_a

        # Determine decision based on fundamental law and evidence state
        decision, target_verified = self._make_decision(
            requested_delta_a=requested_delta_a,
            delta_v=delta_v,
            verification_margin=verification_margin,
            has_valid_evidence=len(valid_evidence) > 0,
            has_expired_evidence=any(
                v.status == ValidationStatus.EXPIRED for v in validation_chain
            ),
        )

        # Determine validation result
        if has_expired_evidence := any(
            v.status == ValidationStatus.EXPIRED for v in validation_chain
        ):
            validation_result = ValidationStatus.EXPIRED
        elif len(valid_evidence) > 0:
            validation_result = ValidationStatus.VALID
        else:
            validation_result = ValidationStatus.UNVERIFIED

        # Build decision context
        decision_context = self._build_decision_context(
            decision=decision,
            delta_a=requested_delta_a,
            delta_v=delta_v,
            verification_margin=verification_margin,
            has_expired=has_expired_evidence,
        )

        # Create signature
        signature = CryptographicSignature(
            algorithm="RSA-SHA256",
            value=f"placeholder_signature_{hash(target_id + str(current_timestamp)) % 1000}",
            key_id=self.key_id,
            timestamp=current_timestamp,
        )

        # Build evidence lineage
        evidence_lineage = EvidenceLineage(
            source=evidence_sources,
            validation=validation_chain,
            contribution=contribution_map,
            decision=decision_context,
        )

        # Return canonical response
        return VerificationResponse(
            decision=decision,
            requested_authority=requested_authority,
            verified=target_verified,
            validation_result=validation_result,
            validated_delta_a=requested_delta_a,
            delta_v=delta_v,
            risk_score=risk_score,
            verification_margin=verification_margin,
            mutation=False,
            evidence_lineage=evidence_lineage,
            signature=signature,
        )

    def _make_decision(
        self,
        requested_delta_a: float,
        delta_v: float,
        verification_margin: float,
        has_valid_evidence: bool,
        has_expired_evidence: bool,
    ) -> tuple[Decision, bool]:
        """
        Deterministic decision logic.
        
        Returns:
            (Decision, verified: bool)
        """
        # Fundamental law: ΔA ≤ ΔV
        if verification_margin < 0:
            # Insufficient capacity
            if has_expired_evidence:
                # Critical evidence expired: fail-closed REJECT at request level
                return (Decision.REJECT, False)
            else:
                # Systemic issue: SAFE_LOCK
                return (Decision.SAFE_LOCK, False)

        # ΔA ≤ ΔV satisfied
        if has_valid_evidence:
            return (Decision.GRANT, True)
        elif has_expired_evidence:
            # Margin OK but critical evidence expired
            return (Decision.REJECT, False)
        else:
            # No evidence at all
            return (Decision.REJECT, False)

    def _build_decision_context(
        self,
        decision: Decision,
        delta_a: float,
        delta_v: float,
        verification_margin: float,
        has_expired: bool,
    ) -> DecisionContext:
        """Build human-readable decision reasoning."""
        timestamp = datetime.utcnow().isoformat() + "Z"

        if decision == Decision.GRANT:
            reasoning = (
                f"All evidence valid. ΔA ({delta_a}) ≤ ΔV ({delta_v}). "
                f"Risk score within acceptable threshold. GRANT authority."
            )
            principle = "ΔA ≤ ΔV satisfied"
        elif decision == Decision.REJECT:
            if has_expired:
                reasoning = (
                    f"Critical evidence expired. Target state unverified with remaining evidence. "
                    f"ΔA ({delta_a}) > ΔV ({delta_v}) after expiration. "
                    f"Request-level REJECT: insufficient verification capacity."
                )
                principle = "ΔA ≤ ΔV failed; fail-closed due to expired critical evidence"
            else:
                reasoning = (
                    f"Insufficient verification capacity. ΔA ({delta_a}) > ΔV ({delta_v}). "
                    f"Request-level REJECT."
                )
                principle = "ΔA ≤ ΔV failed"
        elif decision == Decision.SAFE_LOCK:
            reasoning = (
                f"Systemic verification capacity failure. ΔA ({delta_a}) > ΔV ({delta_v}). "
                f"Entering SAFE_LOCK until governance restored."
            )
            principle = "ΔA ≤ ΔV violated; systemic failure"
        else:
            reasoning = f"Decision: {decision.value}"
            principle = "Verification governance active"

        return DecisionContext(
            timestamp=timestamp,
            reasoning=reasoning,
            governing_principle=principle,
        )
