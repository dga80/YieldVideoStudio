# Task Assignment: E2E Test Writer

You are teamwork_preview_test_writer_e2e.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_test_writer_e2e
Authoritative User Request: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md

## Objective
Implement the comprehensive E2E test suite in `tests/test_e2e_visual_pipeline.py` and publish `TEST_READY.md` at the project root according to the specification in `TEST_INFRA.md` and `PROJECT.md`.

## Test Requirements (Opaque-box, Requirement-driven)
Follow the 4-tier methodology in `TEST_INFRA.md`:
1. **Tier 1 (Feature Coverage)**: Isolated functional tests for all 15 features:
   - F1: Multimodal Style Inversion (`extraer_adn_estilo`)
   - F2: Multimodal Character Inversion (`extraer_anclas_personaje`)
   - F3: Style DNA Caching & Persistence
   - F4: Purge Spanish Meta-Rules (no conversational Spanish in positive prompt)
   - F5: Eliminate Phantom References (no "Reference image" strings)
   - F6: 5-Slot Modular Prompt Architecture ([STYLE DNA], [SCENE/ACTION], [CHARACTER ANCHORS], [LIGHTING], [NEGATIVE PROMPT], <250 tokens / <1000 chars)
   - F7: Dedicated Negative Prompt Isolation
   - F8: Remove 280-Char Prompt Mutilation in `yieldchat_imagen.py`
   - F9: Agnes AI Base64 Delivery (`response_format: b64_json`)
   - F10: Provider Fallback & Circuit Breaker (error handling for 402, 429)
   - F11: Cache Pollution Prevention (no emergency canvases in `banco/imagenes`)
   - F12: Dummy Canvas Detector
   - F13: Histogram & Palette Consistency Judge (Bhattacharyya distance)
   - F14: Framing & Continuity Verification
   - F15: E2E Integration Pipeline
2. **Tier 2 (Boundary & Corner Cases)**:
   - Empty prompts, 0-character inputs, oversized 20,000-character inputs, missing API keys, corrupted image bytes, extreme histogram differences.
3. **Tier 3 (Cross-Feature Combinations)**:
   - Pairwise tests across Inversion ↔ Prompt Builder ↔ Engine Adapter ↔ Visual QA Judge.
4. **Tier 4 (Real-World Application Scenarios)**:
   - 5 end-to-end scenario simulations (S1: Dialogue interior, S2: Confrontation exterior, S3: Shot continuity, S4: Provider failover, S5: Complex multi-rule legacy prompt modernization).

## Key Execution Rules
- Use `unittest` or `pytest` compatible structure.
- Write mock/deterministic fixtures so the entire test suite can run quickly and reliably offline without burning live API credits.
- Also include optional live test hooks if environment keys (`GEMINI_API_KEY`, `AGNES_API_KEY`) are present.
- Execute `python3 -m unittest discover -s tests -p "test_*.py"` to ensure all test files parse and pass or properly mock unbuilt modules gracefully.
- Publish `/Users/danidev/Desktop/asVideoStudio/TEST_READY.md` when the test suite is ready.
- Write `handoff.md` and report back via `send_message`.


## 2026-10-06T19:37:27Z
Received dispatch from parent orchestrator:
Implement the comprehensive E2E test suite in `tests/test_e2e_visual_pipeline.py`.
It must cover all 15 features across Tiers 1-4 (Tier 1: Feature coverage, Tier 2: Boundaries, Tier 3: Pairwise interactions, Tier 4: Real-world scenarios S1-S5).
The test suite must be runnable offline with deterministic mocks and fixtures so it executes in seconds, while also providing integration checks.
Execute the test runner (`python3 -m unittest discover -s tests -p "test_*.py"` or similar) to ensure test execution integrity.
Publish /Users/danidev/Desktop/asVideoStudio/TEST_READY.md when ready.
Write handoff.md and update progress.md in your working directory.
When done, send your completion message back to parent orchestrator.
