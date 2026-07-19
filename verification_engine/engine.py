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
import math
import re
from verification_engine.models import (
    VerificationResponse,
    EvidenceLineage,
    ValidationRecord,
    DecisionContext,
    CryptographicSignature,
    Decision,
    ValidationStatus,
)

# Strict UTC timestamp format required for deterministic cross-language behavior.
_ISO_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# Evidence status handling:
# - "valid" contributes to delta_v only when all timestamp checks pass
# - all other recognized statuses are fail-closed
_RECOGNIZED_EVIDENCE_STATUSES = frozenset({"valid", "expired", "invalid", "unverified"})
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
        target_id = self._validate_non_empty_string(target_id, "target_id")
        requested_authority = self._validate_non_empty_string(
            requested_authority, "requested_authority"
        )
        evidence_items = self._validate_evidence_items(evidence_items)
        requested_delta_a = self._validate_requested_delta_a(requested_delta_a)
        current_dt = self._parse_utc_timestamp(
            current_timestamp, field_name="current_timestamp"
        )

        valid_evidence = []
        evidence_sources: List[str] = []
        validation_chain: List[ValidationRecord] = []
        contribution_map: Dict[str, float] = {}
        total_valid_risk_contribution = 0.0
        has_critical_failure = False
        has_invalid_evidence = False

        # Duplicate-ID detection
        seen_ids: set = set()

        for evidence in evidence_items:
            if not isinstance(evidence, dict):
                raise ValueError("Each evidence item must be an object.")

            evidence_id = evidence.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                raise ValueError("Each evidence item must include a non-empty evidence_id string.")

            source = evidence.get("source")
            if not isinstance(source, str) or not source.strip():
                raise ValueError(
                    f"Evidence '{evidence_id}' must include a non-empty source string."
                )

            timestamp = evidence.get("timestamp")
            evidence_dt = self._parse_utc_timestamp(
                timestamp, field_name=f"evidence '{evidence_id}' timestamp"
            )
            timestamp_for_lineage = timestamp

            expires_at = None
            if "expires_at" in evidence:
                expires_at = self._parse_utc_timestamp(
                    evidence["expires_at"],
                    field_name=f"evidence '{evidence_id}' expires_at",
                )

            data = evidence.get("data")
            if not isinstance(data, dict):
                raise ValueError(
                    f"Evidence '{evidence_id}' data must be an object."
                )
            raw_status = data.get("verification_status", "")
            data_status = raw_status.strip().lower() if isinstance(raw_status, str) else ""
            confidence = self._validate_confidence(
                data.get("confidence"), evidence_id=evidence_id
            )

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

            # 1. verification_status must be recognized and explicitly valid
            if data_status not in _RECOGNIZED_EVIDENCE_STATUSES:
                has_critical_failure = True
                has_invalid_evidence = True
                validation_chain.append(
                    ValidationRecord(
                        evidence_id=evidence_id,
                        timestamp=timestamp_for_lineage,
                        status=ValidationStatus.UNVERIFIED,
                        critical=True,
                    )
                )
                contribution_map[evidence_id] = 0.0
                continue

            # 2. Explicit failure status in evidence data
            if data_status in _CRITICAL_FAILED_STATUSES:
                has_critical_failure = True
                if data_status != "expired":
                    has_invalid_evidence = True
                validation_chain.append(
                    ValidationRecord(
                        evidence_id=evidence_id,
                        timestamp=timestamp_for_lineage,
                        status=ValidationStatus.EXPIRED
                        if data_status == "expired"
                        else ValidationStatus.UNVERIFIED,
                        critical=True,
                    )
                )
                contribution_map[evidence_id] = 0.0
                continue

            # 3. Time-based expiration (expires_at ≤ current_timestamp)
            if expires_at is not None:
                if current_dt >= expires_at:
                    has_critical_failure = True
                    validation_chain.append(
                        ValidationRecord(
                            evidence_id=evidence_id,
                            timestamp=timestamp_for_lineage,
                            status=ValidationStatus.EXPIRED,
                            critical=True,
                        )
                    )
                    contribution_map[evidence_id] = 0.0
                    continue

            # 5. Future-dated evidence (timestamp > current_timestamp)
            if evidence_dt > current_dt:
                has_critical_failure = True
                has_invalid_evidence = True
                validation_chain.append(
                    ValidationRecord(
                        evidence_id=evidence_id,
                        timestamp=timestamp_for_lineage,
                        status=ValidationStatus.UNVERIFIED,
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
                    timestamp=timestamp_for_lineage,
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
        has_failed_evidence = any(v.status != ValidationStatus.VALID for v in validation_chain)
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
            has_expired_evidence = any(
                v.status == ValidationStatus.EXPIRED for v in validation_chain
            )
            if has_expired_evidence:
                validation_result = ValidationStatus.EXPIRED
            elif has_invalid_evidence:
                validation_result = ValidationStatus.INVALID
            else:
                validation_result = ValidationStatus.UNVERIFIED
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
                if verification_margin < 0:
                    reasoning = (
                        f"Critical evidence failed. "
                        f"Request exceeds verification capacity after fail-closed evaluation: "
                        f"ΔA ({delta_a}) > ΔV ({delta_v}). "
                        f"Request-level REJECT."
                    )
                else:
                    reasoning = (
                        f"Critical evidence failed fail-closed validation. "
                        f"Request-level REJECT even though ΔA ({delta_a}) ≤ ΔV ({delta_v})."
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
        - alphabetically sorted keys
        - compact separators ("," and ":") with no extra whitespace
        """
        payload = {
            "key_id": self.key_id,
            "signature_timestamp": current_timestamp,
            "target_id": target_id,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _validate_requested_delta_a(self, requested_delta_a: Any) -> float:
        """
        Validate requested_delta_a as a finite numeric value within [0, 1].

        Note: bool is rejected explicitly even though bool subclasses int in Python.
        """
        # bool is a subclass of int in Python; reject explicitly for strict numeric validation.
        if isinstance(requested_delta_a, bool) or not isinstance(
            requested_delta_a, (int, float)
        ):
            raise ValueError(
                "requested_delta_a must be a finite numeric value in [0.0, 1.0]."
            )
        value = float(requested_delta_a)
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError(
                "requested_delta_a must be a finite numeric value in [0.0, 1.0]."
            )
        return value

    def _validate_non_empty_string(self, value: Any, field_name: str) -> str:
        """Validate required top-level non-empty string fields."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value

    def _validate_evidence_items(self, evidence_items: Any) -> List[Dict[str, Any]]:
        """Validate evidence_items is an ordered list for deterministic processing."""
        if not isinstance(evidence_items, list):
            raise ValueError("evidence_items must be a list.")
        return evidence_items

    def _validate_confidence(self, confidence: Any, evidence_id: str) -> float:
        """Validate confidence is finite numeric in [0.0, 1.0] with bool rejected."""
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError(
                f"Evidence '{evidence_id}' confidence must be a finite numeric value in [0.0, 1.0]."
            )
        value = float(confidence)
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError(
                f"Evidence '{evidence_id}' confidence must be a finite numeric value in [0.0, 1.0]."
            )
        return value

    def _parse_utc_timestamp(self, value: Any, field_name: str) -> datetime:
        """
        Parse strict UTC timestamps of format YYYY-MM-DDTHH:MM:SSZ.
        Offsets like +00:00 are intentionally rejected to keep canonical parity.
        Raises ValueError on missing/malformed values.
        """
        if not isinstance(value, str) or not _ISO_UTC_TIMESTAMP_RE.match(value):
            raise ValueError(
                f"{field_name} must be an ISO 8601 UTC timestamp in format YYYY-MM-DDTHH:MM:SSZ."
            )
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
