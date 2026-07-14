#!/usr/bin/env node

/**
 * Nexus Verification Engine v0.1 - Mock Service
 * Node.js implementation of verification endpoint
 * Single authoritative endpoint with deterministic responses
 * Implements NEXUS-CC-CON-001 contract
 */

const express = require('express');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

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
 * 
 * Request body:
 * {
 *   target_id: string
 *   requested_authority: string
 *   requested_delta_a: number
 *   evidence_items: Array<{
 *     evidence_id: string
 *     source: string
 *     timestamp: string (ISO 8601)
 *     expires_at?: string (ISO 8601)
 *     data: { verification_status: string, confidence: number }
 *   }>
 * }
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
    res.status(500).json({ error: err.message });
  }
});

/**
 * Deterministic verification logic
 */
function verifyRequest(targetId, requestedAuthority, requestedDeltaA, evidenceItems, currentTimestamp) {
  const validEvidence = [];
  const evidenceSources = [];
  const validationChain = [];
  const contributionMap = {};
  let totalValidRiskContribution = 0;

  const currentDt = new Date(currentTimestamp);

  for (const evidence of evidenceItems) {
    const evidenceId = evidence.evidence_id;
    const source = evidence.source;
    const timestamp = evidence.timestamp;
    const confidence = evidence.data?.confidence || 0;

    if (!evidenceSources.includes(source)) {
      evidenceSources.push(source);
    }

    // Check expiration
    if (evidence.expires_at) {
      const expiresAt = new Date(evidence.expires_at);
      if (currentDt >= expiresAt) {
        validationChain.push({
          evidence_id: evidenceId,
          timestamp: timestamp,
          status: 'EXPIRED'
        });
        contributionMap[evidenceId] = 0;
        continue;
      }
    }

    // Evidence is valid
    validEvidence.push(evidence);
    validationChain.push({
      evidence_id: evidenceId,
      timestamp: timestamp,
      status: 'VALID'
    });

    const contribution = confidence * 0.1;
    contributionMap[evidenceId] = contribution;
    totalValidRiskContribution += contribution;
  }

  // Calculate verification capacity and risk
  const deltaV = validEvidence.length > 0 ? 0.75 : 0.0;
  const riskScore = validEvidence.length > 0 
    ? Math.min(0.13, totalValidRiskContribution)
    : Math.max(0.87, totalValidRiskContribution);

  const verificationMargin = deltaV - requestedDeltaA;

  // Determine decision
  const hasExpiredEvidence = validationChain.some(v => v.status === 'EXPIRED');
  let decision, verified;

  if (verificationMargin < 0) {
    decision = hasExpiredEvidence ? 'REJECT' : 'SAFE_LOCK';
    verified = false;
  } else {
    if (validEvidence.length > 0) {
      decision = 'GRANT';
      verified = true;
    } else {
      decision = 'REJECT';
      verified = false;
    }
  }

  const validationResult = hasExpiredEvidence 
    ? 'EXPIRED'
    : (validEvidence.length > 0 ? 'VALID' : 'UNVERIFIED');

  // Build decision context
  const decisionContext = buildDecisionContext(
    decision,
    requestedDeltaA,
    deltaV,
    verificationMargin,
    hasExpiredEvidence
  );

  // Create signature
  const signatureValue = generateSignature(targetId, currentTimestamp);

  // Build response
  const response = {
    decision: decision,
    requested_authority: requestedAuthority,
    verified: verified,
    validation_result: validationResult,
    validated_delta_a: requestedDeltaA,
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
      algorithm: 'RSA-SHA256',
      value: signatureValue,
      key_id: 'KEY-NEXUS-VE-001',
      timestamp: currentTimestamp
    }
  };

  return response;
}

function buildDecisionContext(decision, deltaA, deltaV, verificationMargin, hasExpired) {
  const timestamp = new Date().toISOString();
  let reasoning, principle;

  if (decision === 'GRANT') {
    reasoning = `All evidence valid. ΔA (${deltaA}) ≤ ΔV (${deltaV}). Risk score within acceptable threshold. GRANT authority.`;
    principle = 'ΔA ≤ ΔV satisfied';
  } else if (decision === 'REJECT') {
    if (hasExpired) {
      reasoning = `Critical evidence expired. Target state unverified with remaining evidence. ΔA (${deltaA}) > ΔV (${deltaV}) after expiration. Request-level REJECT: insufficient verification capacity.`;
      principle = 'ΔA ≤ ΔV failed; fail-closed due to expired critical evidence';
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
    timestamp: timestamp,
    reasoning: reasoning,
    governing_principle: principle
  };
}

function generateSignature(targetId, timestamp) {
  const hash = crypto.createHash('sha256');
  hash.update(targetId + timestamp);
  return 'placeholder_signature_' + (Math.abs(hash.digest().readUInt32BE(0)) % 1000);
}

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'nexus-verification-engine-v0.1' });
});

// Server startup
loadFixtures();
const server = app.listen(PORT, () => {
  console.log(`Nexus Verification Engine v0.1 listening on port ${PORT}`);
  console.log('Endpoint: POST /verify');
  console.log('Health: GET /health');
});

module.exports = { app, server };
