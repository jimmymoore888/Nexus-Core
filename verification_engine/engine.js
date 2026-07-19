/**
 * Nexus Verification Engine v0.1.1 — Node.js implementation
 *
 * Core deterministic verification logic implementing NEXUS-CC-CON-001.
 * Fundamental Law: ΔA ≤ ΔV
 *
 * Zero Drift Corrections (v0.1.1):
 * - Critical evidence collapse: expired-by-status, expired-by-time, invalid, unverified,
 *   or future-dated evidence is fail-closed — collapses ΔV to 0.0 and forces REJECT.
 * - validated_delta_a = requested_delta_a for GRANT only; 0.0 for REJECT and SAFE_LOCK.
 * - Duplicate evidence IDs are rejected (throws Error).
 * - risk_score is bounded to [0.0, 1.0].
 * - Evaluation timestamp is determined from the explicit currentTimestamp argument.
 * - Signature now uses deterministic SHA-256-DEMO-DIGEST over canonical payload.
 */

'use strict';

const crypto = require('crypto');

/** Evidence data statuses that constitute a critical failure and collapse ΔV to 0. */
const ISO_UTC_TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const RECOGNIZED_EVIDENCE_STATUSES = new Set(['valid', 'expired', 'invalid', 'unverified']);
const CRITICAL_FAILED_STATUSES = new Set(['expired', 'invalid', 'unverified']);

/**
 * Execute deterministic verification against evidence lineage.
 *
 * @param {string}  targetId           - System identifier being verified
 * @param {string}  requestedAuthority - Authority level requested
 * @param {number}  requestedDeltaA    - Adaptation delta requested (ΔA)
 * @param {Array}   evidenceItems      - Evidence objects with validation metadata
 * @param {string}  currentTimestamp   - Evaluation timestamp (ISO 8601)
 * @returns {object} VerificationResponse with canonical structure
 * @throws {Error} if duplicate evidence IDs are present
 */
function verifyRequest(targetId, requestedAuthority, requestedDeltaA, evidenceItems, currentTimestamp) {
  const normalizedRequestedDeltaA = validateRequestedDeltaA(requestedDeltaA);
  const currentDt = parseUtcTimestamp(currentTimestamp, 'current_timestamp');

  const validEvidence = [];
  const evidenceSources = [];
  const validationChain = [];
  const contributionMap = {};
  let totalValidRiskContribution = 0.0;
  let hasCriticalFailure = false;
  let hasInvalidEvidence = false;

  // Duplicate-ID detection
  const seenIds = new Set();

  for (const evidence of evidenceItems) {
    if (!evidence || typeof evidence !== 'object' || Array.isArray(evidence)) {
      throw new Error('Each evidence item must be an object.');
    }

    const evidenceId = evidence.evidence_id;
    if (typeof evidenceId !== 'string' || evidenceId.trim() === '') {
      throw new Error('Each evidence item must include a non-empty evidence_id string.');
    }

    const source = evidence.source;
    if (typeof source !== 'string' || source.trim() === '') {
      throw new Error(`Evidence '${evidenceId}' must include a non-empty source string.`);
    }

    const timestamp = evidence.timestamp;
    const timestampForLineage = typeof timestamp === 'string' ? timestamp : '';
    const confidence = parseFloat((evidence.data && evidence.data.confidence != null)
      ? evidence.data.confidence : 0.0);
    const rawStatus = evidence.data ? evidence.data.verification_status : '';
    const dataStatus = (typeof rawStatus === 'string') ? rawStatus.trim().toLowerCase() : '';

    // Reject duplicate evidence IDs immediately
    if (seenIds.has(evidenceId)) {
      throw new Error(
        `Duplicate evidence_id detected: '${evidenceId}'. Each evidence item must carry a unique ID.`
      );
    }
    seenIds.add(evidenceId);

    // Track all source identifiers
    if (!evidenceSources.includes(source)) {
      evidenceSources.push(source);
    }

    // --- Critical failure detection (fail-closed) ---

    // 1. verification_status must be recognized and explicitly valid
    if (!RECOGNIZED_EVIDENCE_STATUSES.has(dataStatus)) {
      hasCriticalFailure = true;
      hasInvalidEvidence = true;
      validationChain.push({
        evidence_id: evidenceId,
        timestamp: timestampForLineage,
        status: 'UNVERIFIED',
        critical: true
      });
      contributionMap[evidenceId] = 0.0;
      continue;
    }

    // 2. Explicit failure status in evidence data
    if (CRITICAL_FAILED_STATUSES.has(dataStatus)) {
      hasCriticalFailure = true;
      if (dataStatus !== 'expired') {
        hasInvalidEvidence = true;
      }
      validationChain.push({
        evidence_id: evidenceId,
        timestamp: timestampForLineage,
        status: dataStatus === 'expired' ? 'EXPIRED' : 'UNVERIFIED',
        critical: true
      });
      contributionMap[evidenceId] = 0.0;
      continue;
    }

    // 3. evidence.timestamp is required and strictly validated
    let evidenceDt;
    try {
      evidenceDt = parseUtcTimestamp(timestamp, `evidence '${evidenceId}' timestamp`);
    } catch (_) {
      hasCriticalFailure = true;
      hasInvalidEvidence = true;
      validationChain.push({
        evidence_id: evidenceId,
        timestamp: timestampForLineage,
        status: 'UNVERIFIED',
        critical: true
      });
      contributionMap[evidenceId] = 0.0;
      continue;
    }

    // 4. Time-based expiration (expires_at <= currentTimestamp)
    if (Object.prototype.hasOwnProperty.call(evidence, 'expires_at')) {
      let expiresAt;
      try {
        expiresAt = parseUtcTimestamp(evidence.expires_at, `evidence '${evidenceId}' expires_at`);
      } catch (_) {
        hasCriticalFailure = true;
        hasInvalidEvidence = true;
        validationChain.push({
          evidence_id: evidenceId,
          timestamp: timestampForLineage,
          status: 'UNVERIFIED',
          critical: true
        });
        contributionMap[evidenceId] = 0.0;
        continue;
      }
      if (currentDt >= expiresAt) {
        hasCriticalFailure = true;
        validationChain.push({
          evidence_id: evidenceId,
          timestamp: timestampForLineage,
          status: 'EXPIRED',
          critical: true
        });
        contributionMap[evidenceId] = 0.0;
        continue;
      }
    }

    // 5. Future-dated evidence (timestamp > currentTimestamp)
    if (evidenceDt > currentDt) {
      hasCriticalFailure = true;
      hasInvalidEvidence = true;
      validationChain.push({
        evidence_id: evidenceId,
        timestamp: timestampForLineage,
        status: 'UNVERIFIED',
        critical: true
      });
      contributionMap[evidenceId] = 0.0;
      continue;
    }

    // --- Evidence is valid ---
    validEvidence.push(evidence);
    validationChain.push({
      evidence_id: evidenceId,
      timestamp: timestampForLineage,
      status: 'VALID',
      critical: false
    });

    const contribution = confidence * 0.1;
    contributionMap[evidenceId] = contribution;
    totalValidRiskContribution += contribution;
  }

  // --- Verification capacity and risk score ---
  // Any critical failure collapses ΔV to 0 regardless of co-present valid evidence.
  let deltaV, rawRisk;
  if (validEvidence.length > 0 && !hasCriticalFailure) {
    deltaV = 0.75;
    rawRisk = Math.min(0.13, totalValidRiskContribution);
  } else {
    deltaV = 0.0;
    rawRisk = Math.max(0.87, totalValidRiskContribution);
  }

  // Bound risk_score to [0.0, 1.0]
  const riskScore = Math.max(0.0, Math.min(1.0, rawRisk));

  // Verification margin
  const verificationMargin = deltaV - normalizedRequestedDeltaA;

  // Determine whether any evidence failed
  const hasFailedEvidence = validationChain.some(v => v.status !== 'VALID');

  // Decision logic
  let decision, verified;
  if (verificationMargin < 0) {
    if (hasFailedEvidence) {
      decision = 'REJECT';
    } else {
      decision = 'SAFE_LOCK';
    }
    verified = false;
  } else {
    if (validEvidence.length > 0 && !hasFailedEvidence) {
      decision = 'GRANT';
      verified = true;
    } else {
      decision = 'REJECT';
      verified = false;
    }
  }

  // Validation result
  let validationResult;
  if (hasFailedEvidence) {
    const hasExpired = validationChain.some(v => v.status === 'EXPIRED');
    if (hasExpired) {
      validationResult = 'EXPIRED';
    } else if (hasInvalidEvidence) {
      validationResult = 'INVALID';
    } else {
      validationResult = 'UNVERIFIED';
    }
  } else if (validEvidence.length > 0) {
    validationResult = 'VALID';
  } else {
    validationResult = 'UNVERIFIED';
  }

  // validated_delta_a: requested value for GRANT only; 0.0 for REJECT/SAFE_LOCK
  const validatedDeltaA = decision === 'GRANT' ? normalizedRequestedDeltaA : 0.0;

  // Build decision context using explicit evaluation timestamp
  const decisionContext = buildDecisionContext(
    decision, normalizedRequestedDeltaA, deltaV, verificationMargin, hasFailedEvidence, currentTimestamp
  );

  // Deterministic demo digest over canonical UTF-8 payload.
  const signatureValue = generateSignature(targetId, currentTimestamp);

  return {
    decision: decision,
    requested_authority: requestedAuthority,
    verified: verified,
    validation_result: validationResult,
    validated_delta_a: validatedDeltaA,
    delta_v: deltaV,
    risk_score: riskScore,
    verification_margin: verificationMargin,
    mutation: false,
    evidence_lineage: {
      source: evidenceSources,
      validation: validationChain,
      contribution: contributionMap,
      decision: decisionContext
    },
    signature: {
      algorithm: 'SHA-256-DEMO-DIGEST',
      value: signatureValue,
      key_id: 'KEY-NEXUS-VE-001',
      timestamp: currentTimestamp
    }
  };
}

function buildDecisionContext(decision, deltaA, deltaV, verificationMargin, hasFailed, evaluationTimestamp) {
  let reasoning, principle;

  if (decision === 'GRANT') {
    reasoning = `All evidence valid. ΔA (${deltaA}) ≤ ΔV (${deltaV}). Risk score within acceptable threshold. GRANT authority.`;
    principle = 'ΔA ≤ ΔV satisfied';
  } else if (decision === 'REJECT') {
    if (hasFailed) {
      if (verificationMargin < 0) {
        reasoning = `Critical evidence failed. Request exceeds verification capacity after fail-closed evaluation: ΔA (${deltaA}) > ΔV (${deltaV}). Request-level REJECT.`;
      } else {
        reasoning = `Critical evidence failed fail-closed validation. Request-level REJECT even though ΔA (${deltaA}) ≤ ΔV (${deltaV}).`;
      }
      principle = 'ΔA ≤ ΔV failed; fail-closed due to critical evidence failure';
    } else {
      reasoning = `Insufficient verification capacity. ΔA (${deltaA}) > ΔV (${deltaV}). Request-level REJECT.`;
      principle = 'ΔA ≤ ΔV failed';
    }
  } else if (decision === 'SAFE_LOCK') {
    reasoning = `Systemic verification capacity failure. ΔA (${deltaA}) > ΔV (${deltaV}). Entering SAFE_LOCK until governance restored.`;
    principle = 'ΔA ≤ ΔV violated; systemic failure';
  } else {
    reasoning = `Decision: ${decision}`;
    principle = 'Verification governance active';
  }

  return {
    timestamp: evaluationTimestamp,
    reasoning: reasoning,
    governing_principle: principle
  };
}

function generateSignature(targetId, timestamp) {
  const payload = canonicalStringify({
    key_id: 'KEY-NEXUS-VE-001',
    signature_timestamp: timestamp,
    target_id: targetId
  });
  return crypto.createHash('sha256').update(payload, 'utf8').digest('hex');
}

/**
 * Validate requested_delta_a as a finite Number within [0.0, 1.0].
 * @param {*} value
 * @returns {number}
 */
function validateRequestedDeltaA(value) {
  if (typeof value !== 'number' || Number.isNaN(value) || !Number.isFinite(value)) {
    throw new Error('requested_delta_a must be a finite numeric value in [0.0, 1.0].');
  }
  if (value < 0.0 || value > 1.0) {
    throw new Error('requested_delta_a must be a finite numeric value in [0.0, 1.0].');
  }
  return value;
}

/**
 * Parse strict UTC timestamps in canonical format YYYY-MM-DDTHH:MM:SSZ.
 * The fieldName is included in deterministic validation errors.
 * @param {*} value
 * @param {string} fieldName
 * @returns {Date}
 */
function parseUtcTimestamp(value, fieldName) {
  if (typeof value !== 'string' || !ISO_UTC_TIMESTAMP_RE.test(value)) {
    throw new Error(`${fieldName} must be an ISO 8601 UTC timestamp in format YYYY-MM-DDTHH:MM:SSZ.`);
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`${fieldName} must be an ISO 8601 UTC timestamp in format YYYY-MM-DDTHH:MM:SSZ.`);
  }
  return parsed;
}

// Canonical stringifier for deterministic signature payloads only.
// It must stay aligned with Python json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False).
function canonicalStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalStringify).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return `{${keys.map(key => `${JSON.stringify(key)}:${canonicalStringify(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

module.exports = { verifyRequest, canonicalStringify, generateSignature };
