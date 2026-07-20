"""Bounded TGLR bridge (research demonstration only)."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from verification_engine.engine import VerificationEngine


DEMONSTRATION_SCOPE = "BOUNDED_RESEARCH_DEMONSTRATION_ONLY"


@dataclass
class _ReceiverState:
    states: Dict[str, Dict[str, Any]]


class TGLRBridge:
    """Bounded in-memory bridge from external request envelopes to the verification engine."""

    def __init__(self, allowed_cross_book_pairs: Optional[Set[Tuple[str, str]]] = None) -> None:
        self._engine = VerificationEngine()
        self._allowed_pairs: Set[Tuple[str, str]] = allowed_cross_book_pairs or set()
        self._seen_request_ids: Set[str] = set()
        self._receiver_state: Dict[str, _ReceiverState] = {}
        self._audit_trail: List[Dict[str, Any]] = []

    def verify(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Bridge request must be a JSON object.")

        request_id = self._validate_non_empty_string(payload.get("request_id"), "request_id")
        source_book_id = self._validate_non_empty_string(payload.get("source_book_id"), "source_book_id")
        receiver_book_id = self._validate_non_empty_string(payload.get("receiver_book_id"), "receiver_book_id")
        state_id = self._validate_non_empty_string(payload.get("state_id"), "state_id")
        parent_state_ids = self._validate_parent_state_ids(payload.get("parent_state_ids"))
        target_id = self._validate_non_empty_string(payload.get("target_id"), "target_id")
        requested_authority = self._validate_non_empty_string(
            payload.get("requested_authority"), "requested_authority"
        )
        requested_delta_a = self._validate_unit_interval_number(
            payload.get("requested_delta_a"), "requested_delta_a"
        )
        evaluation_timestamp = self._validate_non_empty_string(
            payload.get("evaluation_timestamp"), "evaluation_timestamp"
        )

        evidence_items = payload.get("evidence_items")
        if not isinstance(evidence_items, list):
            raise ValueError("evidence_items must be a list.")

        if request_id in self._seen_request_ids:
            return self._reject_without_admission(
                request_id=request_id,
                source_book_id=source_book_id,
                receiver_book_id=receiver_book_id,
                state_id=state_id,
                parent_state_ids=parent_state_ids,
                reason="Duplicate request_id rejected.",
            )

        receiver = self._ensure_receiver(receiver_book_id)
        if state_id in receiver.states:
            return self._reject_without_admission(
                request_id=request_id,
                source_book_id=source_book_id,
                receiver_book_id=receiver_book_id,
                state_id=state_id,
                parent_state_ids=parent_state_ids,
                reason="Duplicate state_id rejected.",
            )

        if source_book_id != receiver_book_id and (source_book_id, receiver_book_id) not in self._allowed_pairs:
            return self._reject_without_admission(
                request_id=request_id,
                source_book_id=source_book_id,
                receiver_book_id=receiver_book_id,
                state_id=state_id,
                parent_state_ids=parent_state_ids,
                reason="Unauthorized cross-Book request rejected.",
            )

        if bool(payload.get("direct_memory_write", False)):
            return self._reject_without_admission(
                request_id=request_id,
                source_book_id=source_book_id,
                receiver_book_id=receiver_book_id,
                state_id=state_id,
                parent_state_ids=parent_state_ids,
                reason="Direct memory write request rejected.",
            )

        for parent_id in parent_state_ids:
            if parent_id not in receiver.states:
                return self._reject_without_admission(
                    request_id=request_id,
                    source_book_id=source_book_id,
                    receiver_book_id=receiver_book_id,
                    state_id=state_id,
                    parent_state_ids=parent_state_ids,
                    reason=f"Orphan/nonexistent parent rejected: {parent_id}",
                )

        engine_response = self._engine.verify(
            target_id=target_id,
            requested_authority=requested_authority,
            requested_delta_a=requested_delta_a,
            evidence_items=evidence_items,
            current_timestamp=evaluation_timestamp,
        ).to_dict()

        self._seen_request_ids.add(request_id)

        admitted = engine_response["decision"] == "GRANT"
        if admitted:
            generation = 1 + max(receiver.states[parent_id]["generation"] for parent_id in parent_state_ids)
            receiver.states[state_id] = {
                "state_id": state_id,
                "parent_state_ids": list(parent_state_ids),
                "generation": generation,
                "request_id": request_id,
                "evaluation_timestamp": evaluation_timestamp,
            }
            admission_status = "ADMITTED"
            reason = "State admitted after GRANT."
        else:
            generation = max(receiver.states[parent_id]["generation"] for parent_id in parent_state_ids)
            admission_status = "REJECTED"
            reason = "State not admitted because engine decision was not GRANT."

        digest_ref = self._digest_ref(request_id, state_id, admission_status, engine_response)

        response = {
            "request_id": request_id,
            "source_book_id": source_book_id,
            "receiver_book_id": receiver_book_id,
            "state_id": state_id,
            "decision": engine_response["decision"],
            "admission_status": admission_status,
            "reason": reason,
            "lineage": {
                "parent_state_ids": list(parent_state_ids),
                "connected_to_u0": self._is_connected_to_u0(receiver, parent_state_ids),
                "generation": generation,
            },
            "audit_digest_ref": digest_ref,
            "finite_generation_count": generation,
            "demonstration_scope": DEMONSTRATION_SCOPE,
            "engine_response": engine_response,
        }

        self._audit_trail.append(response)
        return response

    def _reject_without_admission(
        self,
        request_id: str,
        source_book_id: str,
        receiver_book_id: str,
        state_id: str,
        parent_state_ids: List[str],
        reason: str,
    ) -> Dict[str, Any]:
        digest_ref = self._digest_ref(request_id, state_id, "REJECTED", {"decision": "REJECT"})
        response = {
            "request_id": request_id,
            "source_book_id": source_book_id,
            "receiver_book_id": receiver_book_id,
            "state_id": state_id,
            "decision": "REJECT",
            "admission_status": "REJECTED",
            "reason": reason,
            "lineage": {
                "parent_state_ids": list(parent_state_ids),
                "connected_to_u0": False,
                "generation": 0,
            },
            "audit_digest_ref": digest_ref,
            "finite_generation_count": 0,
            "demonstration_scope": DEMONSTRATION_SCOPE,
            "engine_response": None,
        }
        self._audit_trail.append(response)
        return response

    def _ensure_receiver(self, receiver_book_id: str) -> _ReceiverState:
        if receiver_book_id not in self._receiver_state:
            self._receiver_state[receiver_book_id] = _ReceiverState(
                states={
                    "U0": {
                        "state_id": "U0",
                        "parent_state_ids": [],
                        "generation": 0,
                        "request_id": "SYSTEM-U0",
                        "evaluation_timestamp": "1970-01-01T00:00:00Z",
                    }
                }
            )
        return self._receiver_state[receiver_book_id]

    def _is_connected_to_u0(self, receiver: _ReceiverState, parent_state_ids: List[str]) -> bool:
        if not parent_state_ids:
            return False
        return all(parent_id in receiver.states for parent_id in parent_state_ids)

    def _digest_ref(self, request_id: str, state_id: str, admission_status: str, payload: Any) -> str:
        digest_payload = json.dumps(
            {
                "request_id": request_id,
                "state_id": state_id,
                "admission_status": admission_status,
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return f"sha256:{hashlib.sha256(digest_payload.encode('utf-8')).hexdigest()}"

    def _validate_non_empty_string(self, value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value

    def _validate_parent_state_ids(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            raise ValueError("parent_state_ids must be a list.")
        if not value:
            raise ValueError("parent_state_ids must include at least one parent state.")
        out: List[str] = []
        seen: Set[str] = set()
        for parent in value:
            if not isinstance(parent, str) or not parent.strip():
                raise ValueError("parent_state_ids entries must be non-empty strings.")
            if parent in seen:
                raise ValueError("parent_state_ids contains duplicate entries.")
            seen.add(parent)
            out.append(parent)
        return out

    def _validate_unit_interval_number(self, value: Any, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field_name} must be a finite numeric value in [0.0, 1.0].")
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0 or normalized > 1.0:
            raise ValueError(f"{field_name} must be a finite numeric value in [0.0, 1.0].")
        return normalized


def escape_html(value: str) -> str:
    """Escape text for safe local demo rendering."""
    if not isinstance(value, str):
        value = str(value)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
