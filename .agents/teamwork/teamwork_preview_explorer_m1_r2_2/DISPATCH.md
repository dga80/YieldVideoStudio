# Task Assignment: M1 Iteration 2 Explorer 2 - 0-Byte Contract & Cache Validation

You are teamwork_preview_explorer_m1_r2_2.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_2
Authoritative User Request: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md
Project Scope: /Users/danidev/Desktop/asVideoStudio/PROJECT.md
Gate Status: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/orchestrator/GATE_STATUS.md

## Context
Milestone 1 Gate returned REQUEST_CHANGES. Reviewers identified that `test_tier2_b04_zero_byte_image_file` expects an exception (`ValueError`) when given a 0-byte/corrupt file without preset, but `extraer_adn_estilo` silently returned default DNA. Challenger 1 also found that cached character anchors loaded from disk are not validated.

## Instructions
1. Inspect `pasos/inversion_visual.py`:
   - `extraer_adn_estilo`: When `validar_imagen` fails (0-byte or corrupted image) and NO `preset_id` is supplied (or preset is empty/invalid), raise `ValueError(f"Archivo de imagen inválido o corrupto: {ruta_lamina}")` instead of silently returning default DNA.
   - `extraer_anclas_personaje`: Check `_son_anclas_validas(anclas_cache)` before returning cached anchors from `banco/dna/`. If invalid or empty strings, ignore cache and re-extract / fallback.
2. Formulate the exact fix recommendations for the Worker.
3. Write handoff.md, update progress.md, and report back via send_message.


## 2026-10-06T20:12:58Z
You are teamwork_preview_explorer_m1_r2_2.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_2
Read /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md.
Read /Users/danidev/Desktop/asVideoStudio/PROJECT.md.
Read your instructions in /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_2/DISPATCH.md.

Analyze 0-byte corrupt file error contract (raising ValueError when no preset is provided) and cache validation for character anchors in `pasos/inversion_visual.py`.
Recommend specific line-by-line changes for the Worker.
Write handoff.md and send your findings back to the orchestrator.
