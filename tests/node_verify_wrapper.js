'use strict';

const fs = require('fs');
const { verifyRequest } = require('../verification_engine/engine');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));

try {
  const response = verifyRequest(
    input.target_id,
    input.requested_authority,
    input.requested_delta_a,
    input.evidence_items,
    input.current_timestamp
  );
  process.stdout.write(JSON.stringify({ ok: true, response }));
} catch (err) {
  process.stdout.write(JSON.stringify({ ok: false, error: err.message }));
}
