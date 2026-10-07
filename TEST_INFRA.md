# E2E Test Infra: asVideoStudio Visual Fidelity & Engine Resilience

## Test Philosophy
- Opaque-box, requirement-driven testing derived from `ORIGINAL_REQUEST.md` (R1, R2, R3, QA, Acceptance Criteria).
- No dependency on implementation internals; tests exercise public module interfaces and API contracts.
- Systematic 4-tier methodology:
  - **Tier 1 - Feature Coverage**: Direct verification of each of the 15 features in isolation.
  - **Tier 2 - Boundary & Corner Cases**: Empty inputs, oversized inputs, invalid image payloads, network timeouts, special characters, zero characters, max tokens.
  - **Tier 3 - Cross-Feature Interactions**: Pairwise testing across Inversion ↔ Modular Prompt ↔ Engine Adapter ↔ QA Judge.
  - **Tier 4 - Real-World Application Scenarios**: Full pipeline simulations on realistic scenes and characters.

---

## Feature Inventory & Test Coverage
| # | Feature | Source (Requirement) | Tier 1 Tests | Tier 2 Tests | Tier 3 Pairwise | Tier 4 Scenario |
|---|---------|----------------------|:------------:|:------------:|:---------------:|:---------------:|
| 1 | Multimodal Style Inversion | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ | ✓ |
| 2 | Multimodal Character Inversion | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ | ✓ |
| 3 | Style DNA Caching & Persistence | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ | ✓ |
| 4 | Purge Spanish Meta-Rules | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ | ✓ |
| 5 | Eliminate Phantom References | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ | ✓ |
| 6 | 5-Slot Modular Prompt Architecture | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ | ✓ |
| 7 | Dedicated Negative Prompt Isolation | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ | ✓ |
| 8 | Remove 280-Char Prompt Mutilation | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ | ✓ |
| 9 | Agnes AI Base64 Delivery | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ | ✓ |
| 10 | Provider Fallback & Circuit Breaker | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ | ✓ |
| 11 | Cache Pollution Prevention | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ | ✓ |
| 12 | Dummy Canvas Detector | ORIGINAL_REQUEST QA | 5 | 5 | ✓ | ✓ |
| 13 | Histogram & Palette Consistency Judge| ORIGINAL_REQUEST QA | 5 | 5 | ✓ | ✓ |
| 14 | Framing & Continuity Verification | ORIGINAL_REQUEST QA | 5 | 5 | ✓ | ✓ |
| 15 | E2E Integration & Verification | ORIGINAL_REQUEST Acceptance | 5 | 5 | ✓ | ✓ |

---

## Test Architecture
- **Test Runner**: `pytest` or Python unittest (`python3 -m unittest discover -s tests`).
- **Location**: `/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py`.
- **Pass/Fail Semantics**: All test suites must execute and pass with exit code 0.
- **Mocking & Live Policy**:
  - Live network tests verify genuine API contracts with live keys where available.
  - Unit/Boundary tests use deterministic mocks to verify resilience against 404, 402, 429, timeouts, and corrupted payloads without depleting API balances.

---

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Expected Outcome |
|---|----------|--------------------|------------------|
| S1 | Single-character dialogue in interior setting | F1, F2, F3, F6, F9, F13 | Style DNA extracted, character anchored, b64 generated, QA approves |
| S2 | Two-character confrontation in wide exterior | F1, F2, F5, F6, F7, F9, F14 | Both characters anchored, negative prompt isolated, framing verified |
| S3 | Rapid consecutive scenes continuity check | F1, F6, F9, F13, F14 | Palette and luminance continuity within acceptable Bhattacharyya threshold (<0.65) |
| S4 | Provider failover on upstream HTTP 500/404 | F8, F9, F10, F11, F12 | Circuit breaker trips cleanly, fallback provider used, no emergency canvas cached |
| S5 | Complex multi-rule scenario with legacy prompt inputs | F4, F5, F6, F7, F8, F9 | Legacy input stripped of 14 KB Spanish rules, converted to modular English, generated intact |

---

## Coverage Thresholds
- Tier 1: 5 tests × 15 features = 75 test cases (or structured parameterized test classes covering each feature).
- Tier 2: 5 boundary conditions per feature = 75 boundary assertions.
- Tier 3: Pairwise cross-module tests = 15 interaction scenarios.
- Tier 4: Real-world workflow scenarios = 5 complete multi-stage pipelines.
- **Total Minimum**: Comprehensive test runner verifying all 15 features across Tiers 1-4.
