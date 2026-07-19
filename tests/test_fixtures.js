/**
 * Nexus Verification Engine v0.1.1 — Node.js fixture and unit tests
 *
 * Tests cover:
 * - Fixture regression (CAL-001, CAL-002)
 * - Zero Drift invariants (all critical evidence types)
 * - validated_delta_a rules (GRANT vs REJECT/SAFE_LOCK)
 * - Duplicate evidence ID rejection
 * - risk_score bounds
 * - SAFE_LOCK with positive delta_v
 * - Signature label
 */

'use strict';

const assert = require('assert');
const path = require('path');
const fs = require('fs');
const { verifyRequest, canonicalStringify, generateSignature } = require('../verification_engine/engine');

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    process.stdout.write('.');
  } catch (err) {
    failed++;
    failures.push({ name, error: err });
    process.stdout.write('F');
  }
}

function loadFixture(fixtureId) {
  const fixturesDir = path.join(__dirname, '..', 'fixtures');
  const filePath = path.join(fixturesDir, `${fixtureId}.json`);
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

// ---------------------------------------------------------------------------
// Fixture Regression Tests
// ---------------------------------------------------------------------------

test('CAL-001: GRANT with valid evidence', () => {
  const fixture = loadFixture('NEXUS-VE-TEST-CAL-001');
  const req = fixture.request;
  const exp = fixture.expected_response;
  const resp = verifyRequest(
    req.target_id, req.requested_authority, req.requested_delta_a,
    req.evidence_items, '2026-07-14T10:00:01Z'
  );
  assert.strictEqual(resp.decision, 'GRANT');
  assert.strictEqual(resp.verified, true);
  assert.strictEqual(resp.validated_delta_a, exp.validated_delta_a);
  assert.strictEqual(resp.delta_v, exp.delta_v);
  assert.strictEqual(resp.verification_margin, exp.verification_margin);
  assert.strictEqual(resp.risk_score, exp.risk_score);
  assert.strictEqual(resp.mutation, false);
});

test('CAL-002: REJECT due to expired critical evidence', () => {
  const fixture = loadFixture('NEXUS-VE-TEST-CAL-002');
  const req = fixture.request;
  const exp = fixture.expected_response;
  const resp = verifyRequest(
    req.target_id, req.requested_authority, req.requested_delta_a,
    req.evidence_items, '2026-07-14T10:00:02Z'
  );
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.verified, false);
  assert.strictEqual(resp.validation_result, 'EXPIRED');
  assert.strictEqual(resp.validated_delta_a, exp.validated_delta_a);
  assert.strictEqual(resp.delta_v, exp.delta_v);
  assert.strictEqual(resp.verification_margin, exp.verification_margin);
  assert(resp.verification_margin < 0, 'margin must be negative');
});

// ---------------------------------------------------------------------------
// Schema Validation
// ---------------------------------------------------------------------------

test('response has all required fields', () => {
  const resp = verifyRequest('test_001', 'ANALYZE', 0.31, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T10:00:00Z',
      data: { verification_status: 'valid', confidence: 0.95 } }
  ], '2026-07-14T10:00:01Z');
  const required = ['decision', 'requested_authority', 'verified', 'validation_result',
    'validated_delta_a', 'delta_v', 'risk_score', 'verification_margin',
    'mutation', 'evidence_lineage', 'signature'];
  for (const field of required) {
    assert(field in resp, `Missing required field: ${field}`);
  }
});

test('evidence_lineage has correct structure', () => {
  const resp = verifyRequest('test_002', 'ANALYZE', 0.2, [], '2026-07-14T10:00:00Z');
  assert(Array.isArray(resp.evidence_lineage.source));
  assert(Array.isArray(resp.evidence_lineage.validation));
  assert(typeof resp.evidence_lineage.contribution === 'object');
  assert(resp.evidence_lineage.decision !== null);
});

test('signature has all required fields', () => {
  const resp = verifyRequest('test_003', 'ANALYZE', 0.1, [], '2026-07-14T10:00:00Z');
  assert(resp.signature.algorithm, 'algorithm must be present');
  assert(resp.signature.value, 'value must be present');
  assert(resp.signature.key_id, 'key_id must be present');
  assert(resp.signature.timestamp, 'timestamp must be present');
});

// ---------------------------------------------------------------------------
// Zero Drift Invariant Tests
// ---------------------------------------------------------------------------

test('expired-by-time evidence collapses delta_v to 0 (fail-closed)', () => {
  const resp = verifyRequest('exp_time_test', 'ANALYZE', 0.31, [
    { evidence_id: 'E-EXP', source: 'critical', timestamp: '2026-07-13T10:00:00Z',
      expires_at: '2026-07-13T20:00:00Z',
      data: { verification_status: 'valid', confidence: 0.95 } }
  ], '2026-07-13T20:00:01Z');
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.delta_v, 0.0);
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

test('expired-by-status evidence collapses delta_v to 0', () => {
  const resp = verifyRequest('exp_status_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E-STATUS', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'expired', confidence: 0 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.delta_v, 0.0);
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

test('invalid-status evidence collapses delta_v to 0', () => {
  const resp = verifyRequest('invalid_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E-INV', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'invalid', confidence: 0 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.delta_v, 0.0);
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

test('unverified-status evidence collapses delta_v to 0', () => {
  const resp = verifyRequest('unverified_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E-UNV', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'unverified', confidence: 0 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.delta_v, 0.0);
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

test('future-dated evidence collapses delta_v to 0', () => {
  const resp = verifyRequest('future_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E-FUT', source: 'telemetry', timestamp: '2026-07-14T11:00:00Z',
      data: { verification_status: 'valid', confidence: 0.95 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.delta_v, 0.0);
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

test('mixed valid+expired is fail-closed (REJECT, not GRANT)', () => {
  const resp = verifyRequest('mixed_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E-VALID', source: 'current', timestamp: '2026-07-14T10:00:00Z',
      data: { verification_status: 'valid', confidence: 0.95 } },
    { evidence_id: 'E-EXP', source: 'old', timestamp: '2026-07-13T10:00:00Z',
      expires_at: '2026-07-13T20:00:00Z',
      data: { verification_status: 'valid', confidence: 0.90 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.delta_v, 0.0);
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

// ---------------------------------------------------------------------------
// validated_delta_a Rules
// ---------------------------------------------------------------------------

test('GRANT: validated_delta_a equals requested_delta_a', () => {
  const resp = verifyRequest('grant_vda_test', 'ANALYZE', 0.45, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'valid', confidence: 0.9 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'GRANT');
  assert.strictEqual(resp.validated_delta_a, 0.45);
});

test('REJECT: validated_delta_a is 0.0', () => {
  const resp = verifyRequest('reject_vda_test', 'ANALYZE', 0.5, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'invalid', confidence: 0 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'REJECT');
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

test('SAFE_LOCK: validated_delta_a is 0.0', () => {
  const resp = verifyRequest('safe_lock_vda_test', 'ANALYZE', 0.9, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'valid', confidence: 0.9 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.decision, 'SAFE_LOCK');
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

// ---------------------------------------------------------------------------
// SAFE_LOCK: delta_v must remain positive
// ---------------------------------------------------------------------------

test('SAFE_LOCK regression: delta_v > 0 when capacity overrun but no failed evidence', () => {
  const resp = verifyRequest('sl_regression', 'ACTUATE', 0.8, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'valid', confidence: 0.95 } },
    { evidence_id: 'E2', source: 'audit_log', timestamp: '2026-07-14T09:30:00Z',
      data: { verification_status: 'valid', confidence: 0.92 } }
  ], '2026-07-14T10:00:01Z');
  assert.strictEqual(resp.decision, 'SAFE_LOCK');
  assert.strictEqual(resp.delta_v, 0.75);
  assert(resp.verification_margin < 0);
  assert.strictEqual(resp.validated_delta_a, 0.0);
});

// ---------------------------------------------------------------------------
// Additional Integrity
// ---------------------------------------------------------------------------

test('duplicate evidence IDs throw Error', () => {
  let threw = false;
  try {
    verifyRequest('dup_test', 'ANALYZE', 0.2, [
      { evidence_id: 'DUP', source: 'a', timestamp: '2026-07-14T09:00:00Z',
        data: { verification_status: 'valid', confidence: 0.9 } },
      { evidence_id: 'DUP', source: 'b', timestamp: '2026-07-14T09:30:00Z',
        data: { verification_status: 'valid', confidence: 0.8 } }
    ], '2026-07-14T10:00:00Z');
  } catch (e) {
    threw = true;
    assert(e.message.includes('DUP'), 'error must name the duplicate ID');
  }
  assert(threw, 'must throw for duplicate evidence IDs');
});

test('risk_score is bounded to [0, 1]', () => {
  for (const confidence of [0.0, 0.5, 1.0]) {
    const resp = verifyRequest(`risk_${confidence}`, 'ANALYZE', 0.1, [
      { evidence_id: `E-${confidence}`, source: 'telemetry',
        timestamp: '2026-07-14T09:00:00Z',
        data: { verification_status: 'valid', confidence } }
    ], '2026-07-14T10:00:00Z');
    assert(resp.risk_score >= 0.0 && resp.risk_score <= 1.0,
      `risk_score ${resp.risk_score} out of [0,1] for confidence ${confidence}`);
  }
});

test('signature algorithm is SHA-256-DEMO-DIGEST', () => {
  const resp = verifyRequest('sig_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'valid', confidence: 0.9 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.signature.algorithm, 'SHA-256-DEMO-DIGEST');
  assert.strictEqual(resp.signature.timestamp, '2026-07-14T10:00:00Z');
});

test('critical flag is true for failed evidence entries', () => {
  const resp = verifyRequest('critical_true_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E-CRIT', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'expired', confidence: 0.0 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.evidence_lineage.validation[0].critical, true);
});

test('critical flag is false for valid evidence entries', () => {
  const resp = verifyRequest('critical_false_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E-VALID', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'valid', confidence: 0.9 } }
  ], '2026-07-14T10:00:00Z');
  assert.strictEqual(resp.evidence_lineage.validation[0].critical, false);
});

test('canonicalStringify sorts nested keys deterministically', () => {
  const payload = { z: 1, a: { y: 2, x: 3 }, b: [3, { d: 4, c: null }] };
  const expected = '{"a":{"x":3,"y":2},"b":[3,{"c":null,"d":4}],"z":1}';
  assert.strictEqual(canonicalStringify(payload), expected);
  assert.strictEqual(canonicalStringify(payload), expected);
});

test('canonicalStringify handles empty and null values', () => {
  assert.strictEqual(canonicalStringify({}), '{}');
  assert.strictEqual(canonicalStringify({ k: null, a: [] }), '{"a":[],"k":null}');
});

test('generateSignature deterministic with special characters', () => {
  const targetId = 'system/α?=value&x=1';
  const ts = '2026-07-14T10:00:00Z';
  const sig1 = generateSignature(targetId, ts);
  const sig2 = generateSignature(targetId, ts);
  assert.strictEqual(sig1, sig2);
  assert.strictEqual(sig1.length, 64);
});

test('decision context uses evaluation timestamp', () => {
  const evalTs = '2026-07-14T10:00:00Z';
  const resp = verifyRequest('ts_test', 'ANALYZE', 0.2, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'valid', confidence: 0.9 } }
  ], evalTs);
  assert.strictEqual(resp.evidence_lineage.decision.timestamp, evalTs);
});

test('determinism: same input produces same output', () => {
  const args = ['det_test', 'ANALYZE', 0.25, [
    { evidence_id: 'E1', source: 'telemetry', timestamp: '2026-07-14T09:00:00Z',
      data: { verification_status: 'valid', confidence: 0.9 } }
  ], '2026-07-14T10:00:00Z'];
  const r1 = verifyRequest(...args);
  const r2 = verifyRequest(...args);
  const r3 = verifyRequest(...args);
  assert.strictEqual(r1.decision, r2.decision);
  assert.strictEqual(r2.decision, r3.decision);
  assert.strictEqual(r1.delta_v, r2.delta_v);
  assert.strictEqual(r1.validated_delta_a, r2.validated_delta_a);
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log('');
console.log(`Ran ${passed + failed} test(s): ${passed} passed, ${failed} failed`);
if (failures.length > 0) {
  console.error('\nFailures:');
  for (const { name, error } of failures) {
    console.error(`  FAIL: ${name}`);
    console.error(`        ${error.message}`);
  }
  process.exit(1);
} else {
  console.log('OK');
}
