## 2026-10-07T13:38:23Z
You are the Worker for Milestone 1 Iteration 2 (Visual Style & Character DNA Inversion hardening).
Your working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_worker_m1_r2

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Authoritative User Request:
/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md
Please read it first before starting work.

Reference Documents & Detailed Fix Blueprints:
1. /Users/danidev/Desktop/asVideoStudio/PROJECT.md (Interface Contracts)
2. /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_1/handoff.md (Detailed blueprint for null safety, defensive attribute handling, dead code cleanup, and character cache validation)
3. /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_2/handoff.md (Detailed blueprint for 0-byte/corrupt file ValueError contract, _buscar_preset, and cache writer invariants)

Write Ownership:
You exclusively own `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`.
You may also clean up test cache pollution in `banco/dna/` and update `tests/test_stress_inversion_visual.py` if aligning with the ValueError contract.

Tasks to implement in `pasos/inversion_visual.py`:
1. Change 1: Remove dead Pydantic imports and unused StyleDNA / CharacterAnchors classes.
2. Change 2: Harden `describir_paleta_hex` to handle None, non-string, and empty inputs gracefully without raising AttributeError.
3. Change 3: Implement `_buscar_preset(preset_id)` helper and harden `inferir_preset_id` against None and non-dict fields.
4. Change 4: Harden `sintetizar_adn_desde_preset` against None and non-string values across all dictionary fields (medium, palette, trazo, relleno, luz, evitar).
5. Change 5: Add validator `_son_anclas_validas(anclas)` asserting that name and anchors_block are non-empty strings.
6. Change 6: In `extraer_adn_estilo`, enforce that 0-byte or corrupt image files raise `ValueError(f"Archivo de imagen inválido o corrupto: {ruta_lamina}")` unless a valid preset with style guide is provided as fallback.
7. Change 7: In `extraer_anclas_personaje`, validate cache files using `_son_anclas_validas` and harden `_ancla_fallback` against non-string descriptions.
8. Change 8: In `_guardar_cache_huella`, ensure data passes `_es_adn_valido` (for style) or `_son_anclas_validas` (for character) before saving to disk.
9. Cleanup: Remove synthetic test-polluted cache files in `banco/dna/` and `banco/presets/pr1a0eef81dc7/`.

Verification to run:
1. python3 -c "import pasos.inversion_visual as iv; assert isinstance(iv.describir_paleta_hex([None, 123, '#FF0000', True]), str)"
2. python3 pasos/prueba_inversion_visual.py -v
3. python3 -m unittest tests/test_e2e_visual_pipeline.py -k test_tier2_b04_zero_byte_image_file -v
4. python3 -m unittest tests/test_stress_inversion_visual.py -v

Write your completion report to `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_worker_m1_r2/handoff.md` with:
- Summary of changes implemented
- Test commands executed and full stdout/stderr verification outputs
- Code diff/structure
Send a message back when complete.
