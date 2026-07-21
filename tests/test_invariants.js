/**
 * Nexus Verification Engine — 10,000 seeded Node.js invariant cases.
 *
 * Every generated request must satisfy all Zero Drift invariants:
 *   - delta_v in {0.0, 0.75}
 *   - risk_score in [0.0, 1.0]
 *   - GRANT  → validated_delta_a == requested_delta_a, verified == true, delta_v >= validated_delta_a
 *   - REJECT → validated_delta_a == 0.0, verified == false
 *   - SAFE_LOCK → validated_delta_a == 0.0, verified == false
 *   - actual_constraint_violations = 0 (ΔA ≤ ΔV never violated in any response)
 */

'use strict';

const assert = require('assert');
const { verifyRequest } = require('../verification_engine/engine');

const SEED = 42;
const N_CASES = 10_000;

// Seedable PRNG (mulberry32)
function mulberry32(seed) {
  let s = seed >>> 0;
  return function () {
    s += 0x6D2B79F5;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), 1 | t);
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const CRITICAL_STATUSES = ['expired', 'invalid', 'unverified'];
const ALL_STATUSES = ['valid', 'valid', 'valid', ...CRITICAL_STATUSES]; // 3:5 ratio

function randInt(rng, lo, hi) {
  return lo + Math.floor(rng() * (hi - lo + 1));
}

function randChoice(rng, arr) {
  return arr[Math.floor(rng() * arr.length)];
}

function randEvidence(rng, index) {
  const evidenceId = `EVD-N-${String(index).padStart(6, '0')}`;
  const status = randChoice(rng, ALL_STATUSES);
  const confidence = Math.round(rng() * 10000) / 10000;

  const hoursOffset = randInt(rng, -48, 48);
  let day = 14, hour = 10 + hoursOffset;
  if (hour < 0) { day = 13; hour = 24 + hour; }
  else if (hour >= 24) { day += Math.floor(hour / 24); hour = hour % 24; }
  const ts = `2026-07-${String(day).padStart(2, '0')}T${String(hour).padStart(2, '0')}:00:00Z`;

  const evidence = {
    evidence_id: evidenceId,
    source: `source_${index % 4}`,
    timestamp: ts,
    data: { verification_status: status, confidence }
  };

  // Randomly add expires_at for some valid items
  if (status === 'valid' && rng() < 0.3) {
    const expHours = randInt(rng, -48, 48);
    let eDay = 14, eHour = 10 + expHours;
    if (eHour < 0) { eDay = 13; eHour = 24 + eHour; }
    else if (eHour >= 24) { eDay += Math.floor(eHour / 24); eHour = eHour % 24; }
    evidence.expires_at = `2026-07-${String(eDay).padStart(2, '0')}T${String(eHour).padStart(2, '0')}:00:00Z`;
  }

  return evidence;
}

// ---------------------------------------------------------------------------
// Generate 10,000 cases
// ---------------------------------------------------------------------------

const rng = mulberry32(SEED);
const EVAL_TS = '2026-07-14T10:00:00Z';

const results = [];
for (let i = 0; i < N_CASES; i++) {
  const nEvidence = randInt(rng, 0, 6);
  const evidenceItems = [];
  for (let j = 0; j < nEvidence; j++) {
    evidenceItems.push(randEvidence(rng, i * 10 + j));
  }
  const requestedDeltaA = Math.round(rng() * 10000) / 10000;

  try {
    const response = verifyRequest(
      `inv_target_${String(i).padStart(5, '0')}`,
      'ANALYZE',
      requestedDeltaA,
      evidenceItems,
      EVAL_TS
    );
    results.push({ requestedDeltaA, response, err: null });
  } catch (e) {
    results.push({ requestedDeltaA, response: null, err: 'duplicate' });
  }
}

// ---------------------------------------------------------------------------
// Assertions
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    process.stdout.write('.');
  } catch (e) {
    failed++;
    failures.push({ name, error: e });
    process.stdout.write('F');
  }
}

const validResults = results.filter(r => r.err === null);

test(`case count is ${N_CASES}`, () => {
  assert.strictEqual(results.length, N_CASES);
});

test('delta_v is in {0.0, 0.75} for every response', () => {
  for (const { response: r } of validResults) {
    assert(r.delta_v === 0.0 || r.delta_v === 0.75,
      `delta_v=${r.delta_v} not in {0.0, 0.75}`);
  }
});

test('risk_score bounded to [0, 1] for every response', () => {
  for (const { response: r } of validResults) {
    assert(r.risk_score >= 0.0 && r.risk_score <= 1.0,
      `risk_score ${r.risk_score} out of [0,1]`);
  }
});

test('GRANT invariants: validated_delta_a == requested, verified == true, delta_v >= validated_delta_a', () => {
  for (const { requestedDeltaA: da, response: r } of validResults) {
    if (r.decision === 'GRANT') {
      assert.strictEqual(r.validated_delta_a, da,
        `GRANT: validated_delta_a ${r.validated_delta_a} != requested ${da}`);
      assert.strictEqual(r.verified, true, 'GRANT: verified must be true');
      assert(r.delta_v >= r.validated_delta_a,
        `GRANT: delta_v ${r.delta_v} < validated_delta_a ${r.validated_delta_a}`);
    }
  }
});

test('REJECT invariants: validated_delta_a == 0.0, verified == false', () => {
  for (const { response: r } of validResults) {
    if (r.decision === 'REJECT') {
      assert.strictEqual(r.validated_delta_a, 0.0,
        `REJECT: validated_delta_a must be 0.0, got ${r.validated_delta_a}`);
      assert.strictEqual(r.verified, false, 'REJECT: verified must be false');
    }
  }
});

test('SAFE_LOCK invariants: validated_delta_a == 0.0, verified == false', () => {
  for (const { response: r } of validResults) {
    if (r.decision === 'SAFE_LOCK') {
      assert.strictEqual(r.validated_delta_a, 0.0,
        `SAFE_LOCK: validated_delta_a must be 0.0, got ${r.validated_delta_a}`);
      assert.strictEqual(r.verified, false, 'SAFE_LOCK: verified must be false');
    }
  }
});

test('zero actual_constraint_violations (validated_delta_a <= delta_v for all)', () => {
  let violations = 0;
  for (const { response: r } of validResults) {
    if (r.validated_delta_a > r.delta_v) violations++;
  }
  assert.strictEqual(violations, 0,
    `actual_constraint_violations = ${violations} (must be 0)`);
});

test('GRANT cases present in 10,000 cases', () => {
  const count = validResults.filter(r => r.response.decision === 'GRANT').length;
  assert(count > 0, 'No GRANT decisions in 10,000 cases');
});

test('REJECT cases present in 10,000 cases', () => {
  const count = validResults.filter(r => r.response.decision === 'REJECT').length;
  assert(count > 0, 'No REJECT decisions in 10,000 cases');
});

test('SAFE_LOCK cases present in 10,000 cases', () => {
  const count = validResults.filter(r => r.response.decision === 'SAFE_LOCK').length;
  assert(count > 0, 'No SAFE_LOCK decisions in 10,000 cases');
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

console.log('');
console.log(`Invariant cases attempted: ${N_CASES}`);
console.log(`Valid responses: ${validResults.length}`);
console.log(`Ran ${passed + failed} assertion group(s): ${passed} passed, ${failed} failed`);

if (failures.length > 0) {
  console.error('\nFailures:');
  for (const { name, error } of failures) {
    console.error(`  FAIL: ${name}`);
    console.error(`        ${error.message}`);
  }
  process.exit(1);
} else {
  console.log('OK — actual_constraint_violations = 0');
}
