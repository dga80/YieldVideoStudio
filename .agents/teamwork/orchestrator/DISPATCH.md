# Dispatch Instructions

## 2026-10-06T19:23:28Z
You are the Project Orchestrator for this project.

Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/orchestrator
Authoritative User Request: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md

Please read the user request at /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md.
Decompose and execute the mission with specialist subagents:
1. Agente Especialista en Inversión Visual (Vision & Style Inversion Agent)
2. Agente Arquitecto de Prompts de Difusión (Prompt Engineering & Text Encoder Agent)
3. Agente de Integración de Motores y Resiliencia de APIs (Engine Adapter & Network Agent)
4. Agente de Validación y Control de Calidad (Adversarial QA & Style Consistency Judge)

Maintain progress.md and BRIEFING.md in your working directory at /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/orchestrator/.
Ensure all requirements (R1, R2, R3) and acceptance criteria are fully met and verified.
When work is complete and verified, send your final completion report back to me.

## 2026-10-07T13:34:34Z
You are the Project Orchestrator for this project, resuming after an executor timeout restart.

Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/orchestrator
Authoritative User Request: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md
Project Scope & Plan: /Users/danidev/Desktop/asVideoStudio/PROJECT.md
Test Infrastructure: /Users/danidev/Desktop/asVideoStudio/TEST_INFRA.md
E2E Test Certification: /Users/danidev/Desktop/asVideoStudio/TEST_READY.md

Current state in workspace:
- Phase 0 (Survey) was completed.
- E2E Test Suite was implemented in tests/test_e2e_visual_pipeline.py and certified in TEST_READY.md (112 tests, 100% pass).
- Milestone 1 (Visual Style & Character DNA Inversion) Iteration 1 delivered pasos/inversion_visual.py and pasos/prueba_inversion_visual.py (17/17 tests pass).
- Gate check for M1 iteration 1 identified minor edge case hardening needs (0-byte error contract, null field guards in inversion_visual.py, test isolation).
- Iteration 2 explorers (teamwork_preview_explorer_m1_r2_1 and teamwork_preview_explorer_m1_r2_2) have produced detailed handoff reports in .agents/teamwork/ detailing the exact fixes.

Please inspect your working directory (/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/orchestrator/), read BRIEFING.md and progress.md, and resume orchestrating the specialist teams:
1. Complete Milestone 1 hardening and Gate certification.
2. Execute Milestone 2: Modular Prompt Synthesizer (pasos/p6_assets.py).
3. Execute Milestone 3: Resilient Base64 Engine Adapter (motores/imagen_openai/yieldchat_imagen.py).
4. Execute Milestone 4: Adversarial Visual QA Judge (motores/calidad_visual.py).
5. Execute Milestone 5: E2E Integration & Verification against acceptance criteria.

Maintain progress.md and BRIEFING.md in your working directory.
When all acceptance criteria are met and verified, report completion back to me.

## 2026-10-07T18:29:36Z
## DIRECTIVA URGENTE DE CONTENCIÓN DE CUOTA (Instrucción de Usuario)

El usuario ha solicitado expresamente:
"hay alguna manera de que los agentes o tu tarea no consuma la totalidad de mi cuota de gemini?"

Aplica inmediatamente las siguientes medidas de contención:
1. **Reducción radical de concurrencia**: NO lances enjambres masivos de subagentes en paralelo. Cancela o consolida exploradores redundantes.
2. **Aprovechar el trabajo completado**: Los módulos M2 (`p6_assets.py`), M3 (`yieldchat_imagen.py`), M4 (`calidad_visual.py`) y la suite E2E de 112 tests (`tests/test_e2e_visual_pipeline.py`) ya están completamente codificados y pasan en verde.
3. **Puntualidad en M1**: El único detalle pendiente es la eliminación de las dos líneas de atajo ("elena"/"marcus") y la precedencia de caché en `pasos/inversion_visual.py`. Realiza este ajuste con un único Worker enfocado o procede a verificarlo directamente sin rondas redundantes.
4. **Cero llamadas innecesarias a APIs externas**: Toda verificación debe ejecutarse en modo local/offline sin consumir cuota de visión en bucle.
5. **Cierre y reporte final**: Una vez validado localmente el código saneado, consolida el reporte final de victoria para el Victory Auditor.
