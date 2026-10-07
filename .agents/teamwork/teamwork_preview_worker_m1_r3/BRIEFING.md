# BRIEFING — 2026-10-07T18:20:00Z

## Mission
Eliminate hardcoded character fixtures and shortcuts in `pasos/inversion_visual.py`, ensure content disk cache precedence over test mode/API in `extraer_anclas_personaje`, isolate `BANCO` in test suites to prevent cache pollution, and clean repository cache directories.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_worker_m1_r3
- Original parent: a2210173-5f9d-40f1-91e1-d1e85811a249
- Milestone: Milestone 1 Iteration 3 (Source Integrity & Character Cache Precedence Fix)

## 🔒 Key Constraints
- DO NOT CHEAT: No hardcoded test results, facade implementations, or circumventing tasks.
- Make `_ancla_fallback` purely generic based strictly on `nombre` and `descripcion_fallback`.
- In `extraer_anclas_personaje`: Check disk cache first before test mode and Gemini API. Remove `or "elena" in n_low or "marcus" in n_low`.
- Isolate `inversion_visual.BANCO` to temporary directories in `tests/test_e2e_visual_pipeline.py` and `pasos/prueba_inversion_visual.py`.
- Purge synthetic test cache files from `banco/dna/` and `banco/presets/`.

## Current Parent
- Conversation ID: a2210173-5f9d-40f1-91e1-d1e85811a249
- Updated: not yet

## Task Summary
- **What to build**:
  1. Fix `_ancla_fallback` in `pasos/inversion_visual.py` to be completely generic without Elena/Marcus checks.
  2. Fix `extraer_anclas_personaje`: validate path, validate image, check disk cache FIRST (Step 3), check test mode/gemini availability (Step 4, without name hacks), call Gemini Vision (Step 5).
  3. Isolate `BANCO` in `tests/test_e2e_visual_pipeline.py` and `pasos/prueba_inversion_visual.py`.
  4. Clean `banco/dna/` and `banco/presets/`.
- **Success criteria**:
  - Reproduction commands 1 and 2 pass.
  - Adversarial test `test_character_anchors_cache_persistence_and_hit` passes.
  - `pasos/prueba_inversion_visual.py` passes.
  - Zero-byte boundary test passes.
  - Full E2E suite passes.
  - Cache directories remain 100% clean after test runs.
- **Interface contracts**: `/Users/danidev/Desktop/asVideoStudio/PROJECT.md`
- **Code layout**: `/Users/danidev/Desktop/asVideoStudio/PROJECT.md § Code Layout`

## Key Decisions Made
- [TBD]

## Artifact Index
- DISPATCH.md — Initial dispatch assignment
- BRIEFING.md — Working memory
- progress.md — Heartbeat and status log
- handoff.md — Final handoff report

## Change Tracker
- **Files modified**: None yet
- **Build status**: Pending implementation
- **Pending issues**: None

## Quality Status
- **Build/test result**: Pending
- **Lint status**: Pending
- **Tests added/modified**: Pending

## Loaded Skills
- None specified for this task.
