This zip contains replacement tests for the old `test_select_hip_claims_are_rate_limited`.

These tests reflect the approved lane semantic:
- select_hip no longer performs attachment / claiming
- attachment remains a separate domain
- select_hip only participates in live motion selection
- motion still requires ownership
