#!/usr/bin/env node

/**
 * Nexus Verification Engine v0.1.1 - Mock Service
 * Node.js implementation of verification endpoint
 * Single authoritative endpoint with deterministic responses
 * Implements NEXUS-CC-CON-001 contract
 */

const express = require('express');
const fs = require('fs');
const path = require('path');
const { verifyRequest } = require('./verification_engine/engine');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Load fixtures for regression testing
const FIXTURES_DIR = path.join(__dirname, 'fixtures');
const fixtures = {};

function loadFixtures() {
  try {
    const files = fs.readdirSync(FIXTURES_DIR).filter(f => f.endsWith('.json'));
    for (const file of files) {
      const filePath = path.join(FIXTURES_DIR, file);
      const content = fs.readFileSync(filePath, 'utf8');
      fixtures[file.replace('.json', '')] = JSON.parse(content);
    }
    console.log(`Loaded ${Object.keys(fixtures).length} fixture(s)`);
  } catch (err) {
    console.error('Failed to load fixtures:', err.message);
  }
}

/**
 * Deterministic verification endpoint
 * POST /verify
 */
app.post('/verify', (req, res) => {
  try {
    const {
      target_id,
      requested_authority,
      requested_delta_a,
      evidence_items
    } = req.body;

    // Validate request
    if (!target_id || !requested_authority || requested_delta_a === undefined || !evidence_items) {
      return res.status(400).json({
        error: 'Missing required fields: target_id, requested_authority, requested_delta_a, evidence_items'
      });
    }

    const now = new Date().toISOString();
    const response = verifyRequest(
      target_id,
      requested_authority,
      requested_delta_a,
      evidence_items,
      now
    );

    res.json(response);
  } catch (err) {
    console.error('Verification error:', err);
    if (err.message && err.message.startsWith('Duplicate evidence_id')) {
      return res.status(400).json({ error: err.message });
    }
    res.status(500).json({ error: err.message });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'nexus-verification-engine-v0.1.1' });
});

// Server startup
loadFixtures();
const server = app.listen(PORT, () => {
  console.log(`Nexus Verification Engine v0.1.1 listening on port ${PORT}`);
  console.log('Endpoint: POST /verify');
  console.log('Health: GET /health');
});

module.exports = { app, server };
