## 2026-10-07T18:18:36Z

You are the Worker for Milestone 1 Iteration 3 (Source Integrity & Character Cache Precedence Fix).
Your working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_worker_m1_r3

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Authoritative User Request:
/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md
Please read it first before starting work.

Reference Documents:
- /Users/danidev/Desktop/asVideoStudio/PROJECT.md
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_reviewer_m1_r2_1/handoff.md
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_reviewer_m1_r2_2/handoff.md
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r3_1/BRIEFING.md

Write Ownership:
- Target files:
  1. `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`
  2. Test files for cache isolation: `tests/test_e2e_visual_pipeline.py`, `pasos/prueba_inversion_visual.py`
  3. Clean cache directories: `banco/dna/`, `banco/presets/`

Specific Tasks in `pasos/inversion_visual.py`:
1. In `_ancla_fallback()` (lines 681-692):
   Completely remove hardcoded test character name checks (`if "elena" in n_low:` and `elif "marcus" in n_low:`).
   Make `_ancla_fallback()` purely generic based strictly on `nombre` and `descripcion_fallback`.
2. In `extraer_anclas_personaje` (lines 694-735):
   - Handle `ruta_personaje is None or not str(ruta_personaje).strip()` early (return `_ancla_fallback()`).
   - Validate physical image file (0-byte / corrupt raises `ValueError`).
   - Check content disk cache `banco/dna/personaje_{huella}.json` as Step 3 (FIRST before test mode or Gemini API check).
   - Check `os.environ.get("ESTUDIO_MODO_TEST") == "1" or not gemini_cliente.hay_gemini()` as Step 4 (completely remove `or "elena" in n_low or "marcus" in n_low`).
   - Call Gemini Vision as Step 5 and write valid response to cache.
3. Test Cache Isolation:
   In test classes (`test_e2e_visual_pipeline.py` and `pasos/prueba_inversion_visual.py`), isolate `inversion_visual.BANCO` to a temporary directory during test setup/teardown so running tests does NOT leave synthetic files in production `banco/dna/` or `banco/presets/`.
4. Clean up any synthetic test files currently in `banco/dna/` and `banco/presets/`.
