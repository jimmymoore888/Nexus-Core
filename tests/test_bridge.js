'use strict';

const assert = require('assert');
const { TGLRBridge, escapeHtml } = require('../tglr_bridge/bridge');

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

function baseRequest() {
  return {
    request_id: 'REQ-001',
    source_book_id: 'BOOK-A',
    receiver_book_id: 'BOOK-A',
    state_id: 'STATE-001',
    parent_state_ids: ['U0'],
    target_id: 'system_001',
    requested_delta_a: 0.3,
    requested_authority: 'ANALYZE',
    evaluation_timestamp: '2026-07-20T00:00:00Z',
    evidence_items: [{
      evidence_id: 'EVD-001',
      source: 'telemetry',
      timestamp: '2026-07-19T23:59:59Z',
      data: { verification_status: 'valid', confidence: 0.95 }
    }]
  };
}

(function main() {
  const bridge = new TGLRBridge();

  test('GRANT admits state', () => {
    const response = bridge.verify(baseRequest());
    assert.strictEqual(response.decision, 'GRANT');
    assert.strictEqual(response.admission_status, 'ADMITTED');
    assert(response.engine_response.validated_delta_a <= response.engine_response.delta_v);
  });

  test('REJECT does not admit', () => {
    const req = baseRequest();
    req.request_id = 'REQ-002';
    req.state_id = 'STATE-002';
    req.evidence_items = [{
      evidence_id: 'EVD-002',
      source: 'telemetry',
      timestamp: '2026-07-19T23:59:59Z',
      data: { verification_status: 'invalid', confidence: 0.1 }
    }];
    const response = bridge.verify(req);
    assert.strictEqual(response.decision, 'REJECT');
    assert.strictEqual(response.admission_status, 'REJECTED');
  });

  test('SAFE_LOCK does not admit', () => {
    const req = baseRequest();
    req.request_id = 'REQ-003';
    req.state_id = 'STATE-003';
    req.requested_delta_a = 0.95;
    const response = bridge.verify(req);
    assert.strictEqual(response.decision, 'SAFE_LOCK');
    assert.strictEqual(response.admission_status, 'REJECTED');
  });

  test('duplicate request rejected', () => {
    const req = baseRequest();
    req.request_id = 'REQ-004';
    req.state_id = 'STATE-004';
    bridge.verify(req);
    const dup = { ...req, state_id: 'STATE-005' };
    const response = bridge.verify(dup);
    assert.strictEqual(response.decision, 'REJECT');
    assert(/Duplicate request_id/.test(response.reason));
  });

  test('orphan parent rejected', () => {
    const req = baseRequest();
    req.request_id = 'REQ-006';
    req.state_id = 'STATE-006';
    req.parent_state_ids = ['MISSING'];
    const response = bridge.verify(req);
    assert.strictEqual(response.admission_status, 'REJECTED');
    assert(/Orphan\/nonexistent parent/.test(response.reason));
  });

  test('malformed requested_delta_a throws InputValidationError', () => {
    const req = baseRequest();
    req.request_id = 'REQ-007';
    req.requested_delta_a = '0.3';
    assert.throws(() => bridge.verify(req), /requested_delta_a/);
  });

  test('escape html for demo output', () => {
    assert.strictEqual(
      escapeHtml('<script>alert("x")</script>'),
      '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;'
    );
  });

  test('100 admitted states growth proxy', () => {
    const growthBridge = new TGLRBridge();
    let parent = 'U0';
    for (let i = 1; i <= 100; i++) {
      const req = baseRequest();
      req.request_id = `REQ-G-${i}`;
      req.state_id = `STATE-G-${i}`;
      req.parent_state_ids = [parent];
      req.evidence_items = [{
        evidence_id: `EVD-G-${i}`,
        source: 'telemetry',
        timestamp: '2026-07-19T23:59:59Z',
        data: { verification_status: 'valid', confidence: 0.99 }
      }];
      const response = growthBridge.verify(req);
      assert.strictEqual(response.admission_status, 'ADMITTED');
      assert.strictEqual(response.lineage.generation, i);
      assert.strictEqual(response.lineage.connected_to_u0, true);
      parent = req.state_id;
    }
  });

  console.log('');
  console.log(`Ran ${passed + failed} bridge test(s): ${passed} passed, ${failed} failed`);
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
})();
