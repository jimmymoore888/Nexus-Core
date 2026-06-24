# Nexus SATDS – Threat Dismantling Report

## Summary

- Threats tested: 6
- Threats stopped before core: 6
- Threats reaching core (but held): 0
- actual_constraint_violations: 0
- verification_debt_created: False
- total_verification_debt: 0.00000000
- containment_success_rate: 1.0000
- weakest_layer: Governance
- strongest_layer: Verification

## Per-Threat Results

### Surface-MalformedInputs
- Layer: Surface
- Description: Malformed signals, extreme noise, and false confidence across all sources with large environment shifts.
- Governors activated: MetaVerificationMatrix, SafeLock, AdaptiveWeightEngine
- Reached core: False
- Containment result: **contained**
- Safe Lock events: 57
- Containment events: 0
- Recovery events: 0
- actual_constraint_violations: 0
- verification_debt: 0.00000000

### Signal-CorruptedSource
- Layer: Signal
- Description: One source delivers systematically corrupted scores (near 0) while three sources report honest high-quality signals, creating a detectable outlier.
- Governors activated: MetaVerificationMatrix, SafeLock, AdaptiveWeightEngine
- Reached core: False
- Containment result: **contained**
- Safe Lock events: 1
- Containment events: 0
- Recovery events: 0
- actual_constraint_violations: 0
- verification_debt: 0.00000000

### Verification-InflatedBudget
- Layer: Verification
- Description: All sources report maximum possible signal (1.0) to inflate the verification budget (ΔV) and claim unlimited adaptation.
- Governors activated: AdaptiveWeightEngine
- Reached core: False
- Containment result: **contained**
- Safe Lock events: 0
- Containment events: 0
- Recovery events: 0
- actual_constraint_violations: 0
- verification_debt: 0.00000000

### Influence-WeightPoisoning
- Layer: Influence
- Description: One source alternates between 1.0 and 0.0 to poison the adaptive weight engine and attempt a source monopoly.
- Governors activated: MetaVerificationMatrix, SafeLock, AdaptiveWeightEngine
- Reached core: False
- Containment result: **contained**
- Safe Lock events: 150
- Containment events: 0
- Recovery events: 0
- actual_constraint_violations: 0
- verification_debt: 0.00000000

### Governance-SafeLockAbuse
- Layer: Governance
- Description: Alternating maximally-divergent and aligned signals to repeatedly toggle Safe Lock and attempt containment bypass.
- Governors activated: MetaVerificationMatrix, SafeLock, AdaptiveWeightEngine
- Reached core: False
- Containment result: **contained**
- Safe Lock events: 150
- Containment events: 0
- Recovery events: 0
- actual_constraint_violations: 0
- verification_debt: 0.00000000

### Core-DirectBreachAttempt
- Layer: Core
- Description: Maximum possible signals with a hostile spike every cycle to attempt to force adaptation without sufficient verification.
- Governors activated: Containment, AdaptiveWeightEngine
- Reached core: False
- Containment result: **contained**
- Safe Lock events: 0
- Containment events: 300
- Recovery events: 0
- actual_constraint_violations: 0
- verification_debt: 0.00000000

