# Nexus Napalm Test Suite Report

- All worlds passed: **True**

## Per-World Results

### Napalm-FalseSignal — PASS
- Description: 25% of sources deliver false signals (near 0) while the rest report high confidence, creating persistent false-positive pressure.
- max_da_dv_ratio: 0.016169
- mean_da_dv_ratio: 0.014413
- final_verification_reserve: 1996.470797
- final_verification_debt: 0.000000
- actual_constraint_violations: 0
- attempted_constraint_violations: 0
- governance_intervention_count: 1
- cycles_to_breach: -1

### Napalm-Inflation — PASS
- Description: All sources report maximum signal (1.0) every cycle, attempting to self-award unlimited ΔV and force maximum ΔA.
- max_da_dv_ratio: 0.060000
- mean_da_dv_ratio: 0.060000
- final_verification_reserve: 4700.000000
- final_verification_debt: 0.000000
- actual_constraint_violations: 0
- attempted_constraint_violations: 0
- governance_intervention_count: 0
- cycles_to_breach: -1

### Napalm-ReserveDrain — PASS
- Description: All sources report minimum signal (0.0) to drive ΔV to zero while demanding maximum ΔA, attempting verification starvation.
- max_da_dv_ratio: 0.000000
- mean_da_dv_ratio: 0.000000
- final_verification_reserve: 0.000000
- final_verification_debt: 300.000000
- actual_constraint_violations: 0
- attempted_constraint_violations: 5000
- governance_intervention_count: 0
- cycles_to_breach: 1

### Napalm-Byzantine — PASS
- Description: Two of four sources are colluding (one pair always near 0, the other pair always near 1), creating maximum internal disagreement.
- max_da_dv_ratio: 0.021415
- mean_da_dv_ratio: 0.001438
- final_verification_reserve: 1298.170311
- final_verification_debt: 0.000000
- actual_constraint_violations: 0
- attempted_constraint_violations: 0
- governance_intervention_count: 1
- cycles_to_breach: -1

### Napalm-Recursive — PASS
- Description: Signals oscillate between extremes (0.0↔1.0) each cycle to create resonance instability in the verification engine.
- max_da_dv_ratio: 3.000000
- mean_da_dv_ratio: 1.530612
- final_verification_reserve: 2300.000000
- final_verification_debt: 100.000000
- actual_constraint_violations: 0
- attempted_constraint_violations: 0
- governance_intervention_count: 0
- cycles_to_breach: -1

### Napalm-Lockdown — PASS
- Description: Maximally divergent signals with hostile spikes every cycle to force repeated Safe Lock activations and deny recovery.
- max_da_dv_ratio: 0.023529
- mean_da_dv_ratio: 0.001135
- final_verification_reserve: 1273.552405
- final_verification_debt: 0.000000
- actual_constraint_violations: 0
- attempted_constraint_violations: 0
- governance_intervention_count: 1
- cycles_to_breach: -1

