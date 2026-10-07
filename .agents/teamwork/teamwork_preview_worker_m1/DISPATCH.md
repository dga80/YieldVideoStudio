# Task Assignment: M1 Worker - Visual Style & Character DNA Inversion

You are teamwork_preview_worker_m1.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_worker_m1
Authoritative User Request: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md
Project Scope: /Users/danidev/Desktop/asVideoStudio/PROJECT.md

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## File Ownership
You exclusively own:
- `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`
- `/Users/danidev/Desktop/asVideoStudio/pasos/prueba_inversion_visual.py`

DO NOT modify `pasos/p6_assets.py` or `yieldchat_imagen.py` (owned by downstream milestones).

## Inputs & Research Artifacts to Read
Read the reports delivered by the M1 Explorers before implementing:
- `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_1/analysis.md` (Vision Prompts, Gemini SDK, Schemas)
- `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_2/analysis.md` (Cache layout, disk paths)
- `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_3/analysis.md` (4-tier resilience cascade, color namer, emergency canvas detection)
- `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_3/proposed_prueba_inversion_visual.py` (Test blueprint)

## Deliverables
1. Implement `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py` with:
   - `extraer_adn_estilo(ruta_lamina: str, preset_id: str = None) -> dict`
   - `extraer_anclas_personaje(ruta_personaje: str, nombre_personaje: str, descripcion_fallback: str = "") -> dict`
   - Strict adherence to the contract schema in `PROJECT.md § Interface Contracts`.
   - 4-tier resilience cascade: Cache -> Gemini 2.5 Flash Vision -> Presets Guia Heuristic -> Universal Default DNA.
   - Emergency canvas and corrupted image detector to avoid style poisoning.
   - Content-addressed disk caching in `banco/presets/{preset_id}/dna_estilo.json` and `banco/dna/`.
2. Implement `/Users/danidev/Desktop/asVideoStudio/pasos/prueba_inversion_visual.py` and run it via terminal:
   - Must run all test scenarios and pass 100% with exit code 0.
3. Write `handoff.md` and report back via `send_message` with build/test commands and output.


## 2026-10-06T19:48:15Z
You are teamwork_preview_worker_m1.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_worker_m1
Read /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md first.
Read /Users/danidev/Desktop/asVideoStudio/PROJECT.md.
Read your full instructions in /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_worker_m1/DISPATCH.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

You exclusively own:
- /Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py
- /Users/danidev/Desktop/asVideoStudio/pasos/prueba_inversion_visual.py

Implement `pasos/inversion_visual.py` according to `PROJECT.md § Interface Contracts` and the Explorer reports in:
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_1/analysis.md
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_2/analysis.md
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_3/analysis.md

Implement and run the test suite `pasos/prueba_inversion_visual.py` to verify 100% test pass.
Write handoff.md and update progress.md in your working directory.
When done, send your completion message back to parent orchestrator with test execution details.
