'use strict';

const fs = require('fs');
const path = require('path');
const { TGLRBridge } = require(path.join(__dirname, '..', 'tglr_bridge', 'bridge'));

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const bridge = new TGLRBridge();

try {
  const response = bridge.verify(input);
  process.stdout.write(JSON.stringify({ ok: true, response }));
} catch (err) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(err && err.message ? err.message : err) }));
}
