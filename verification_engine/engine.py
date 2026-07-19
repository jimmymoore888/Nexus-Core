"""
Nexus Verification Engine v0.1.1

Core deterministic verification logic implementing NEXUS-CC-CON-001.
Fundamental Law: ΔA ≤ ΔV

Zero Drift Corrections (v0.1.1):
- Critical evidence collapse: expired-by-status, expired-by-time, invalid, unverified,
  or future-dated evidence is fail-closed — collapses ΔV to 0.0 and forces REJECT.
- validated_delta_a = requested_delta_a for GRANT only; 0.0 for REJECT and SAFE_LOCK.
- Duplicate evidence IDs are rejected (ValueError).
- risk_score is bounded to [0.0, 1.0].
- Evaluation timestamp is determined from the explicit current_timestamp argument.
- Signature uses deterministic SHA-256-DEMO-DIGEST over canonical payload.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any
import hashlib
import json
from verification_engine.models import (
    VerificationResponse,
    EvidenceLineage,
    ValidationRecord,
    DecisionContext,
    CryptographicSignature,
    Decision,
    ValidationStatus,
)

# Evidence data statuses that constitute a critical failure and collapse ΔV to 0.
_CRITICAL_FAILED_STATUSES = frozenset({"expired", "invalid", "unverified"})


class VerificationEngine:
    """
    Deterministic verification engine governed by ΔA ≤ ΔV.

    Properties:
    - Deterministic: same input always produces same output
    - Fail-closed: critical evidence failure collapses ΔV to 0, forces REJECT
    - Auditable: all decisions reproducible from evidence_lineage
    - Conformant: never permits ΔA > ΔV in operational state
    - Zero Drift: validated_delta_a equals requested_delta_a only on GRANT; 0.0 otherwise
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
            current_timestamp: Evaluation timestamp for expiration checks (ISO 8601)

        Returns:
            VerificationResponse with canonical structure

        Raises:
            ValueError: If evidence is malformed, required fields are missing,
                        or duplicate evidence IDs are present
        """
        # Evaluation timestamp — derived from the explicit caller-supplied value
        current_dt = datetime.fromisoformat(current_timestamp.replace("Z", "+00:00"))

        valid_evidence = []
        evidence_sources: List[str] = []
        validation_chain: List[ValidationRecord] = []
        contribution_map: Dict[str, float] = {}
        total_valid_risk_contribution = 0.0
        has_critical_failure = False

        # Duplicate-ID detection
        seen_ids: set = set()

        for evidence in evidence_items:
            evidence_id = evidence["evidence_id"]
            source = evidence["source"]
            timestamp = evidence["timestamp"]
            confidence = float(evidence.get("data", {}).get("confidence", 0.0))
            data_status = str(evidence.get("data", {}).get("verification_status", "")).lower()

            # Reject duplicate evidence IDs immediately
            if evidence_id in seen_ids:
                raise ValueError(
                    f"Duplicate evidence_id detected: '{evidence_id}'. "
                    "Each evidence item must carry a unique ID."
                )
            seen_ids.add(evidence_id)

            # Track all source identifiers
            if source not in evidence_sources:
                evidence_sources.append(source)

            # --- Critical failure detection (fail-closed) ---

            # 1. Explicit failure status in evidence data
            if data_status in _CRITICAL_FAILED_STATUSES:
                has_critical_failure = True
                validation_chain.append(
                    ValidationRecord(
                        evidence_id=evidence_id,
                        timestamp=timestamp,
                        status=ValidationStatus.EXPIRED
                        if data_status == "expired"
                        else ValidationStatus.INVALID,
                        critical=True,
                    )
                )
                contribution_map[evidence_id] = 0.0
                continue

            # 2. Time-based expiration (expires_at ≤ current_timestamp)
            if "expires_at" in evidence:
                expires_at = datetime.fromisoformat(
                    evidence["expires_at"].replace("Z", "+00:00")
                )
                if current_dt >= expires_at:
                    has_critical_failure = True
                    validation_chain.append(
                        ValidationRecord(
                            evidence_id=evidence_id,
                            timestamp=timestamp,
                            status=ValidationStatus.EXPIRED,
                            critical=True,
                        )
                    )
                    contribution_map[evidence_id] = 0.0
                    continue

            # 3. Future-dated evidence (timestamp > current_timestamp)
            try:
                evidence_dt = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                )
                if evidence_dt > current_dt:
                    has_critical_failure = True
                    validation_chain.append(
                        ValidationRecord(
                            evidence_id=evidence_id,
                            timestamp=timestamp,
                            status=ValidationStatus.INVALID,
                            critical=True,
                        )
                    )
                    contribution_map[evidence_id] = 0.0
                    continue
            except ValueError:
                # Unparseable timestamp — treat as invalid
                has_critical_failure = True
                validation_chain.append(
                    ValidationRecord(
                        evidence_id=evidence_id,
                        timestamp=timestamp,
                        status=ValidationStatus.INVALID,
                        critical=True,
                    )
                )
                contribution_map[evidence_id] = 0.0
                continue

            # --- Evidence is valid ---
            valid_evidence.append(evidence)
            validation_chain.append(
                ValidationRecord(
                    evidence_id=evidence_id,
                    timestamp=timestamp,
                    status=ValidationStatus.VALID,
                    critical=False,
                )
            )

            contribution = confidence * 0.1  # simple contribution model
            contribution_map[evidence_id] = contribution
            total_valid_risk_contribution += contribution

        # --- Verification capacity and risk score ---
        # Any critical failure collapses ΔV to 0 regardless of co-present valid evidence.
        if valid_evidence and not has_critical_failure:
            delta_v = 0.75
            raw_risk = min(0.13, total_valid_risk_contribution)
        else:
            delta_v = 0.0
            raw_risk = max(0.87, total_valid_risk_contribution)

        # Bound risk_score to [0.0, 1.0]
        risk_score = max(0.0, min(1.0, raw_risk))

        # Verification margin
        verification_margin = delta_v - requested_delta_a

        # Determine decision
        has_failed_evidence = any(
            v.status in (ValidationStatus.EXPIRED, ValidationStatus.INVALID)
            for v in validation_chain
        )
        decision, target_verified = self._make_decision(
            requested_delta_a=requested_delta_a,
            delta_v=delta_v,
            verification_margin=verification_margin,
            has_valid_evidence=bool(valid_evidence),
            has_failed_evidence=has_failed_evidence,
        )

        # Validation result
        if has_failed_evidence:
            # Prefer EXPIRED over INVALID for backward compat with fixtures
            validation_result = (
                ValidationStatus.EXPIRED
                if any(v.status == ValidationStatus.EXPIRED for v in validation_chain)
                else ValidationStatus.INVALID
            )
        elif valid_evidence:
            validation_result = ValidationStatus.VALID
        else:
            validation_result = ValidationStatus.UNVERIFIED

        # validated_delta_a: requested value for GRANT only; 0.0 for REJECT/SAFE_LOCK
        validated_delta_a = requested_delta_a if decision == Decision.GRANT else 0.0

        # Build decision context using explicit evaluation timestamp
        decision_context = self._build_decision_context(
            decision=decision,
            delta_a=requested_delta_a,
            delta_v=delta_v,
            verification_margin=verification_margin,
            has_failed=has_failed_evidence,
            evaluation_timestamp=current_timestamp,
        )

        # Deterministic demo digest over canonical UTF-8 payload.
        signature_payload = self._build_signature_payload(target_id, current_timestamp)
        signature = CryptographicSignature(
            algorithm="SHA-256-DEMO-DIGEST",
            value=hashlib.sha256(signature_payload.encode("utf-8")).hexdigest(),
            key_id=self.key_id,
            timestamp=current_timestamp,
        )

        evidence_lineage = EvidenceLineage(
            source=evidence_sources,
            validation=validation_chain,
            contribution=contribution_map,
            decision=decision_context,
        )

        return VerificationResponse(
            decision=decision,
            requested_authority=requested_authority,
            verified=target_verified,
            validation_result=validation_result,
            validated_delta_a=validated_delta_a,
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
        has_failed_evidence: bool,
    ) -> tuple:
        """
        Deterministic decision logic enforcing ΔA ≤ ΔV.

        Returns:
            (Decision, verified: bool)
        """
        if verification_margin < 0:
            # ΔA > ΔV — insufficient capacity
            if has_failed_evidence:
                # Fail-closed REJECT at request level
                return (Decision.REJECT, False)
            else:
                # Systemic capacity failure — SAFE_LOCK
                return (Decision.SAFE_LOCK, False)

        # ΔA ≤ ΔV satisfied
        if has_valid_evidence and not has_failed_evidence:
            return (Decision.GRANT, True)
        elif has_failed_evidence:
            # Margin appears OK but critical evidence failed — REJECT
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
        has_failed: bool,
        evaluation_timestamp: str,
    ) -> DecisionContext:
        """Build human-readable decision reasoning using explicit evaluation timestamp."""
        if decision == Decision.GRANT:
            reasoning = (
                f"All evidence valid. ΔA ({delta_a}) ≤ ΔV ({delta_v}). "
                f"Risk score within acceptable threshold. GRANT authority."
            )
            principle = "ΔA ≤ ΔV satisfied"
        elif decision == Decision.REJECT:
            if has_failed:
                reasoning = (
                    f"Critical evidence failed. Target state unverified with remaining evidence. "
                    f"ΔA ({delta_a}) > ΔV ({delta_v}) after failure. "
                    f"Request-level REJECT: insufficient verification capacity."
                )
                principle = "ΔA ≤ ΔV failed; fail-closed due to critical evidence failure"
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
            timestamp=evaluation_timestamp,
            reasoning=reasoning,
            governing_principle=principle,
        )

    def _build_signature_payload(self, target_id: str, current_timestamp: str) -> str:
        """
        Build canonical signature payload shared with Node.js implementation.

        Format requirements for cross-process parity:
        - UTF-8 JSON serialization
        - lexicographically sorted keys
        - compact separators ("," and ":") with no extra whitespace
        """
        payload = {
            "key_id": self.key_id,
            "signature_timestamp": current_timestamp,
            "target_id": target_id,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
