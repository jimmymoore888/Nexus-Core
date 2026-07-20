'use strict';

const assert = require('assert');
const http = require('http');
const path = require('path');
const { spawn } = require('child_process');

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  return fn()
    .then(() => {
      passed++;
      process.stdout.write('.');
    })
    .catch((err) => {
      failed++;
      failures.push({ name, error: err });
      process.stdout.write('F');
    });
}

function postJson(port, pathName, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port,
        path: pathName,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body)
        }
      },
      (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          let parsed = {};
          try { parsed = data ? JSON.parse(data) : {}; } catch (_) {}
          resolve({ statusCode: res.statusCode, body: parsed });
        });
      }
    );
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function startServer() {
  const port = 5100 + Math.floor(Math.random() * 2000);
  const child = spawn('node', ['server.js'], {
    cwd: path.join(__dirname, '..'),
    env: { ...process.env, PORT: String(port) },
    stdio: ['ignore', 'pipe', 'pipe']
  });

  return new Promise((resolve, reject) => {
    let settled = false;
    let stderrBuffer = '';
    const timeout = setTimeout(() => {
      if (!settled) {
        settled = true;
        child.kill('SIGTERM');
        reject(new Error(`Server start timed out. stderr: ${stderrBuffer.trim()}`));
      }
    }, 5000);

    child.stdout.on('data', (buf) => {
      const msg = buf.toString('utf8');
      if (!settled && msg.includes('listening on port')) {
        settled = true;
        clearTimeout(timeout);
        resolve({ child, port });
      }
    });

    child.stderr.on('data', (buf) => {
      stderrBuffer += buf.toString('utf8');
    });

    child.on('exit', (code) => {
      if (!settled) {
        settled = true;
        clearTimeout(timeout);
        reject(new Error(`Server exited before startup (code=${code}). stderr: ${stderrBuffer.trim()}`));
      }
    });
  });
}

function basePayload() {
  return {
    request_id: 'BR-REQ-001',
    source_book_id: 'BOOK-A',
    receiver_book_id: 'BOOK-A',
    state_id: 'BR-STATE-001',
    parent_state_ids: ['U0'],
    target_id: 'system_001',
    requested_authority: 'ANALYZE',
    requested_delta_a: 0.25,
    evaluation_timestamp: '2026-07-20T00:00:00Z',
    evidence_items: [{
      evidence_id: 'EVD-001',
      source: 'telemetry',
      timestamp: '2026-07-19T23:59:59Z',
      data: { verification_status: 'valid', confidence: 0.95 }
    }]
  };
}

async function main() {
  const { child, port } = await startServer();
  try {
    await test('bridge endpoint returns GRANT and admission metadata', async () => {
      const res = await postJson(port, '/bridge/verify', basePayload());
      assert.strictEqual(res.statusCode, 200);
      assert.strictEqual(res.body.decision, 'GRANT');
      assert.strictEqual(res.body.admission_status, 'ADMITTED');
      assert.strictEqual(res.body.engine_response.decision, 'GRANT');
    });

    await test('bridge malformed request returns 400', async () => {
      const payload = basePayload();
      payload.requested_delta_a = '0.2';
      const res = await postJson(port, '/bridge/verify', payload);
      assert.strictEqual(res.statusCode, 400);
      assert(/requested_delta_a/.test(res.body.error));
    });

    await test('bridge duplicate request_id rejects', async () => {
      const p1 = basePayload();
      p1.request_id = 'BR-REQ-002';
      p1.state_id = 'BR-STATE-002';
      const p2 = { ...p1, state_id: 'BR-STATE-003' };
      const first = await postJson(port, '/bridge/verify', p1);
      const second = await postJson(port, '/bridge/verify', p2);
      assert.strictEqual(first.statusCode, 200);
      assert.strictEqual(second.statusCode, 200);
      assert.strictEqual(second.body.admission_status, 'REJECTED');
      assert(/Duplicate request_id/.test(second.body.reason));
    });

    await test('bridge rejects unauthorized cross-book request', async () => {
      const p = basePayload();
      p.request_id = 'BR-REQ-003';
      p.state_id = 'BR-STATE-004';
      p.source_book_id = 'BOOK-B';
      p.receiver_book_id = 'BOOK-A';
      const res = await postJson(port, '/bridge/verify', p);
      assert.strictEqual(res.statusCode, 200);
      assert.strictEqual(res.body.decision, 'REJECT');
      assert(/Unauthorized cross-Book/.test(res.body.reason));
    });

    await test('bridge response is deterministic for identical request on fresh server state', async () => {
      const p = basePayload();
      p.request_id = 'BR-REQ-004';
      p.state_id = 'BR-STATE-005';
      const first = await postJson(port, '/bridge/verify', p);
      const second = await postJson(port, '/verify', {
        target_id: p.target_id,
        requested_authority: p.requested_authority,
        requested_delta_a: p.requested_delta_a,
        evaluation_timestamp: p.evaluation_timestamp,
        evidence_items: p.evidence_items
      });
      assert.strictEqual(first.statusCode, 200);
      assert.strictEqual(second.statusCode, 200);
      assert.strictEqual(first.body.engine_response.decision, second.body.decision);
      assert.strictEqual(first.body.engine_response.signature.value, second.body.signature.value);
    });
  } finally {
    child.kill('SIGTERM');
  }

  console.log('');
  console.log(`Ran ${passed + failed} bridge server test(s): ${passed} passed, ${failed} failed`);
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
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
