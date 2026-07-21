'use strict';

const crypto = require('crypto');
const { verifyRequest, InputValidationError } = require('../verification_engine/engine');

const DEMONSTRATION_SCOPE = 'BOUNDED_RESEARCH_DEMONSTRATION_ONLY';

class TGLRBridge {
  constructor(options = {}) {
    this.allowedPairs = new Set((options.allowedCrossBookPairs || []).map(([a, b]) => `${a}=>${b}`));
    this.seenRequestIds = new Set();
    this.receiverState = new Map();
    this.auditTrail = [];
  }

  verify(payload) {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      throw new InputValidationError('Bridge request must be a JSON object.');
    }

    const requestId = validateNonEmptyString(payload.request_id, 'request_id');
    const sourceBookId = validateNonEmptyString(payload.source_book_id, 'source_book_id');
    const receiverBookId = validateNonEmptyString(payload.receiver_book_id, 'receiver_book_id');
    const stateId = validateNonEmptyString(payload.state_id, 'state_id');
    const parentStateIds = validateParentStateIds(payload.parent_state_ids);
    const targetId = validateNonEmptyString(payload.target_id, 'target_id');
    const requestedAuthority = validateNonEmptyString(payload.requested_authority, 'requested_authority');
    const requestedDeltaA = validateUnitIntervalNumber(payload.requested_delta_a, 'requested_delta_a');
    const evaluationTimestamp = validateNonEmptyString(payload.evaluation_timestamp, 'evaluation_timestamp');

    if (!Array.isArray(payload.evidence_items)) {
      throw new InputValidationError('evidence_items must be an array.');
    }

    if (this.seenRequestIds.has(requestId)) {
      return this.rejectWithoutAdmission({
        requestId,
        sourceBookId,
        receiverBookId,
        stateId,
        parentStateIds,
        reason: 'Duplicate request_id rejected.'
      });
    }

    const receiver = this.ensureReceiver(receiverBookId);
    if (receiver.states.has(stateId)) {
      return this.rejectWithoutAdmission({
        requestId,
        sourceBookId,
        receiverBookId,
        stateId,
        parentStateIds,
        reason: 'Duplicate state_id rejected.'
      });
    }

    if (sourceBookId !== receiverBookId && !this.allowedPairs.has(`${sourceBookId}=>${receiverBookId}`)) {
      return this.rejectWithoutAdmission({
        requestId,
        sourceBookId,
        receiverBookId,
        stateId,
        parentStateIds,
        reason: 'Unauthorized cross-Book request rejected.'
      });
    }

    if (Boolean(payload.direct_memory_write)) {
      return this.rejectWithoutAdmission({
        requestId,
        sourceBookId,
        receiverBookId,
        stateId,
        parentStateIds,
        reason: 'Direct memory write request rejected.'
      });
    }

    for (const parentId of parentStateIds) {
      if (!receiver.states.has(parentId)) {
        return this.rejectWithoutAdmission({
          requestId,
          sourceBookId,
          receiverBookId,
          stateId,
          parentStateIds,
          reason: `Orphan/nonexistent parent rejected: ${parentId}`
        });
      }
    }

    const engineResponse = verifyRequest(
      targetId,
      requestedAuthority,
      requestedDeltaA,
      payload.evidence_items,
      evaluationTimestamp
    );

    this.seenRequestIds.add(requestId);

    const admitted = engineResponse.decision === 'GRANT';
    let generation;
    let admissionStatus;
    let reason;

    if (admitted) {
      generation = 1 + Math.max(...parentStateIds.map((id) => receiver.states.get(id).generation));
      receiver.states.set(stateId, {
        state_id: stateId,
        parent_state_ids: [...parentStateIds],
        generation,
        request_id: requestId,
        evaluation_timestamp: evaluationTimestamp
      });
      admissionStatus = 'ADMITTED';
      reason = 'State admitted after GRANT.';
    } else {
      generation = Math.max(...parentStateIds.map((id) => receiver.states.get(id).generation));
      admissionStatus = 'REJECTED';
      reason = 'State not admitted because engine decision was not GRANT.';
    }

    const response = {
      request_id: requestId,
      source_book_id: sourceBookId,
      receiver_book_id: receiverBookId,
      state_id: stateId,
      decision: engineResponse.decision,
      admission_status: admissionStatus,
      reason,
      lineage: {
        parent_state_ids: [...parentStateIds],
        connected_to_u0: parentStateIds.every((id) => receiver.states.has(id)),
        generation
      },
      audit_digest_ref: digestRef(requestId, stateId, admissionStatus, engineResponse),
      finite_generation_count: generation,
      demonstration_scope: DEMONSTRATION_SCOPE,
      engine_response: engineResponse
    };

    this.auditTrail.push(response);
    return response;
  }

  rejectWithoutAdmission({ requestId, sourceBookId, receiverBookId, stateId, parentStateIds, reason }) {
    const response = {
      request_id: requestId,
      source_book_id: sourceBookId,
      receiver_book_id: receiverBookId,
      state_id: stateId,
      decision: 'REJECT',
      admission_status: 'REJECTED',
      reason,
      lineage: {
        parent_state_ids: [...parentStateIds],
        connected_to_u0: false,
        generation: 0
      },
      audit_digest_ref: digestRef(requestId, stateId, 'REJECTED', { decision: 'REJECT' }),
      finite_generation_count: 0,
      demonstration_scope: DEMONSTRATION_SCOPE,
      engine_response: null
    };
    this.auditTrail.push(response);
    return response;
  }

  ensureReceiver(receiverBookId) {
    if (!this.receiverState.has(receiverBookId)) {
      const states = new Map();
      states.set('U0', {
        state_id: 'U0',
        parent_state_ids: [],
        generation: 0,
        request_id: 'SYSTEM-U0',
        evaluation_timestamp: '1970-01-01T00:00:00Z'
      });
      this.receiverState.set(receiverBookId, { states });
    }
    return this.receiverState.get(receiverBookId);
  }
}

function validateNonEmptyString(value, fieldName) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new InputValidationError(`${fieldName} must be a non-empty string.`);
  }
  return value;
}

function validateParentStateIds(value) {
  if (!Array.isArray(value)) {
    throw new InputValidationError('parent_state_ids must be an array.');
  }
  if (value.length === 0) {
    throw new InputValidationError('parent_state_ids must include at least one parent state.');
  }
  const out = [];
  const seen = new Set();
  for (const parent of value) {
    if (typeof parent !== 'string' || parent.trim() === '') {
      throw new InputValidationError('parent_state_ids entries must be non-empty strings.');
    }
    if (seen.has(parent)) {
      throw new InputValidationError('parent_state_ids contains duplicate entries.');
    }
    seen.add(parent);
    out.push(parent);
  }
  return out;
}

function validateUnitIntervalNumber(value, fieldName) {
  if (typeof value !== 'number' || Number.isNaN(value) || !Number.isFinite(value)) {
    throw new InputValidationError(`${fieldName} must be a finite numeric value in [0.0, 1.0].`);
  }
  if (value < 0.0 || value > 1.0) {
    throw new InputValidationError(`${fieldName} must be a finite numeric value in [0.0, 1.0].`);
  }
  return value;
}

function canonicalStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalStringify).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalStringify(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function digestRef(requestId, stateId, admissionStatus, payload) {
  const canonical = canonicalStringify({ request_id: requestId, state_id: stateId, admission_status: admissionStatus, payload });
  return `sha256:${crypto.createHash('sha256').update(canonical, 'utf8').digest('hex')}`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

module.exports = { TGLRBridge, DEMONSTRATION_SCOPE, escapeHtml };
