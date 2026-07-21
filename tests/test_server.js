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

function postJson(port, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port,
        path: '/verify',
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
  const port = 3100 + Math.floor(Math.random() * 2000);
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

async function main() {
  const { child, port } = await startServer();

  const basePayload = {
    target_id: 'server_test_target',
    requested_authority: 'ANALYZE',
    requested_delta_a: 0.2,
    evidence_items: [
      {
        evidence_id: 'E1',
        source: 'telemetry',
        timestamp: '2026-07-14T09:00:00Z',
        data: { verification_status: 'valid', confidence: 0.9 }
      }
    ],
    evaluation_timestamp: '2026-07-14T10:00:00Z'
  };

  try {
    await test('server returns 400 for invalid requested_delta_a type', async () => {
      const payload = { ...basePayload, requested_delta_a: '0.2' };
      const res = await postJson(port, payload);
      assert.strictEqual(res.statusCode, 400);
      assert(/requested_delta_a/.test(res.body.error));
    });

    await test('server returns 400 when evaluation_timestamp missing', async () => {
      const payload = { ...basePayload };
      delete payload.evaluation_timestamp;
      const res = await postJson(port, payload);
      assert.strictEqual(res.statusCode, 400);
      assert(/evaluation_timestamp/.test(res.body.error));
    });

    await test('server returns 400 for malformed evaluation_timestamp', async () => {
      const payload = { ...basePayload, evaluation_timestamp: '2026/07/14 10:00:00' };
      const res = await postJson(port, payload);
      assert.strictEqual(res.statusCode, 400);
      assert(/current_timestamp|ISO 8601 UTC/.test(res.body.error));
    });

    await test('server returns 400 for malformed input adversarial cases', async () => {
      const cases = [
        {
          name: 'target_id non-string',
          payload: { ...basePayload, target_id: null },
          pattern: /target_id must be a non-empty string/
        },
        {
          name: 'requested_authority non-string',
          payload: { ...basePayload, requested_authority: null },
          pattern: /requested_authority must be a non-empty string/
        },
        {
          name: 'evidence_items object',
          payload: { ...basePayload, evidence_items: {} },
          pattern: /evidence_items must be an array/
        },
        {
          name: 'evidence item non-object',
          payload: { ...basePayload, evidence_items: ['bad'] },
          pattern: /Each evidence item must be an object/
        },
        {
          name: 'evidence.data non-object',
          payload: {
            ...basePayload,
            evidence_items: [
              {
                evidence_id: 'E1',
                source: 'telemetry',
                timestamp: '2026-07-14T09:00:00Z',
                data: 'bad'
              }
            ]
          },
          pattern: /data must be an object/
        },
        {
          name: 'confidence attack string',
          payload: {
            ...basePayload,
            evidence_items: [
              {
                evidence_id: 'E1',
                source: 'telemetry',
                timestamp: '2026-07-14T09:00:00Z',
                data: { verification_status: 'valid', confidence: 'bad' }
              }
            ]
          },
          pattern: /confidence must be a finite numeric value/
        },
        {
          name: 'malformed evidence timestamp with unknown status',
          payload: {
            ...basePayload,
            evidence_items: [
              {
                evidence_id: 'E1',
                source: 'telemetry',
                timestamp: 'not-a-timestamp',
                data: { verification_status: 'mystery', confidence: 0.5 }
              }
            ]
          },
          pattern: /timestamp must be an ISO 8601 UTC timestamp/
        },
        {
          name: 'malformed expires_at',
          payload: {
            ...basePayload,
            evidence_items: [
              {
                evidence_id: 'E1',
                source: 'telemetry',
                timestamp: '2026-07-14T09:00:00Z',
                expires_at: 'bad-expiration',
                data: { verification_status: 'valid', confidence: 0.9 }
              }
            ]
          },
          pattern: /expires_at must be an ISO 8601 UTC timestamp/
        }
      ];

      for (const tc of cases) {
        const res = await postJson(port, tc.payload);
        assert.strictEqual(res.statusCode, 400, `${tc.name} should return HTTP 400`);
        assert(tc.pattern.test(res.body.error), `${tc.name} error mismatch: ${res.body.error}`);
      }
    });

    await test('identical request + evaluation_timestamp is deterministic over HTTP', async () => {
      const res1 = await postJson(port, basePayload);
      const res2 = await postJson(port, basePayload);
      assert.strictEqual(res1.statusCode, 200);
      assert.strictEqual(res2.statusCode, 200);
      assert.deepStrictEqual(res1.body, res2.body);
      assert.strictEqual(res1.body.signature.timestamp, basePayload.evaluation_timestamp);
      assert.strictEqual(
        res1.body.evidence_lineage.decision.timestamp,
        basePayload.evaluation_timestamp
      );
    });
  } finally {
    child.kill('SIGTERM');
  }

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
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
