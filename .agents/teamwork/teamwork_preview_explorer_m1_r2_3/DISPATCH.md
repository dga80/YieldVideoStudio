# Task Assignment: M1 Iteration 2 Explorer 3 - Test Isolation & Offline Determinism

You are teamwork_preview_explorer_m1_r2_3.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_3
Authoritative User Request: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md
Project Scope: /Users/danidev/Desktop/asVideoStudio/PROJECT.md
Gate Status: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/orchestrator/GATE_STATUS.md

## Context
Milestone 1 Gate returned REQUEST_CHANGES. Reviewers noted that running `python3 -m unittest discover -s tests -p "test_*.py"` caused live unmocked Gemini Vision API calls on synthetic test images, causing failures on brittle string assertions, and pollutes production `banco/dna/` with test data.

## Instructions
1. Inspect `tests/test_e2e_visual_pipeline.py` and `tests/test_stress_inversion_visual.py`.
2. Determine how test execution should isolate cache directories (e.g. using `tempfile.TemporaryDirectory` or test cache path override) and ensure test runs mock the live vision API unless explicit live flag is given, so tests run 100% deterministically and offline in seconds.
3. Formulate the exact fix recommendations.
4. Write handoff.md, update progress.md, and report back via send_message.

## 2026-10-06T20:12:58Z
You are teamwork_preview_explorer_m1_r2_3.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_3
Read /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md.
Read /Users/danidev/Desktop/asVideoStudio/PROJECT.md.
Read your instructions in /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_3/DISPATCH.md.

Analyze test suite isolation and offline determinism for `tests/test_e2e_visual_pipeline.py` and `tests/test_stress_inversion_visual.py`.
Determine how to ensure zero live API leakage on synthetic shapes and zero pollution of production `banco/dna/`.
Write handoff.md and send your findings back to the orchestrator.
