# Razorpay Track 04 Evaluation Log

## RZ-EVAL-001
Severity: CRITICAL
Component: Exception Detection
Status: NEW BUG FOUND IN 3-WAY MATCHING

Observation:
- Latest adversarial test (adversarial_eval_6233) shows 0% exception detection
- 46 expected exceptions, 0 detected
- 46 exceptions created in system but none match ground truth scenarios
- Batch metrics: 296 records, 101 auto matched, 17 ML recovered, 3 manual review, 11 unresolved

Evidence:
- trace_single_transaction.py shows:
  - EVAL_TXN_0082 (complex_mismatch): CORRECTLY matched with 0.75 confidence and flagged as amount_mismatch ✓
  - EVAL_TXN_0043 (delayed_settlement): Matched with 0.98 confidence but NO exception ✗
    - GW=46536, LD=46536, BK=45437.75 (bank differs)
    - Reason says "Exact 3-way match" but amounts differ - BUG in 3-way matching logic
  - EVAL_TXN_0071 (same_ref_diff_amount): GW/LD matched by ML (0.37) instead of deterministic ✗
  - EVAL_TXN_0008 (partial_match): GW/LD matched by ML (0.37) instead of deterministic ✗

Root cause:
- **BUG IN 3-WAY MATCHING**: When gateway and ledger amounts match but bank differs, the code assigns 0.98 confidence instead of 0.85
  - Line 126-129 in deterministic.py: checks gw_ld_match and gw_bk_match
  - If gw_ld_match is True but gw_bk_match is False, it should use 0.85 confidence
  - But the logic is incorrectly using 0.98 (EXACT_3WAY_CONFIDENCE)
- **ORDER_ID MATCHING NOT WORKING**: 2-way matches (GW-LD) with same order_id are being matched by ML instead of deterministic
  - This suggests the order_id matching logic is not being executed or is being bypassed

Fix:
- Fix 3-way matching confidence assignment logic
- Debug why order_id matching is not working
- Ensure decision engine properly flags amount mismatches

Validation:
- 3-way matching partially working but confidence assignment is wrong
- Order_id matching completely broken

