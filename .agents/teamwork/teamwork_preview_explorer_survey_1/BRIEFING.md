# BRIEFING — 2026-10-06T19:33:00Z

## Mission
Survey prompt construction architecture, locate Spanish meta-rules, phantom references, engine flow, and propose modular English prompt format.

## 🔒 My Identity
- Archetype: explorer
- Roles: Read-only investigation: analyze problems, synthesize findings, produce structured reports
- Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1
- Original parent: 9b5a6257-25d0-4e41-8283-7957c59e0602
- Milestone: Survey 1 - Prompt Engineering & Text Encoder Architecture

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Focus on prompt construction, Spanish meta-rules, phantom references, engine flow, modular English prompt design
- Write report to survey_prompt.md, write handoff.md, update progress.md, send message to parent

## Current Parent
- Conversation ID: 9b5a6257-25d0-4e41-8283-7957c59e0602
- Updated: 2026-10-06T19:33:00Z

## Investigation State
- **Explored paths**: `pasos/p6_assets.py`, `motores/reglas/reglas.json`, `motores/reglas/reglas.py`, `motores/imagen_openai/yieldchat_imagen.py`, `motores/imagen_openai/imagen.py`, `pasos/estilo.py`, `pasos/moodboard.py`, `pasos/corrector.py`, `pasos/redactor.py`, `pasos/direccion.py`, `pasos/catalogo_visual.py`, `ajustes.json`, `presets.json`.
- **Key findings**:
  1. `p6_assets._prompt_completo` builds massive 10.6K–19.2K character prompts (~2,600–4,800 tokens), overflowing CLIP (77 tokens) and T5 context windows.
  2. `motores/reglas/reglas.json` holds 24 KB total (18 KB content) with 9 rules injecting 5,660 chars of conversational Spanish and rules into `prompt_imagen`, leaking negative concepts into positive attention space.
  3. Image generation engines (Agnes AI, SiliconFlow, Gemini) are called as pure text-to-image endpoints in `yieldchat_imagen.py` with zero image attachments; textual commands like "Reference image 1 is a STYLE SHEET" are phantom references inducing hallucinations.
  4. `yieldchat_imagen.py` hard-truncates prompts to <= 280 characters and overwrites them with boilerplate ("2D vector animation style, clean line art..."), destroying 98% of prompt style/character details.
  5. Agnes AI omits `"response_format": "b64_json"` leading to 404 ephemeral URL drops.
  6. Designed 5-slot Modular English Prompt schema: `[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, `[NEGATIVE PROMPT]` under 250 tokens (~1,000 chars).
- **Unexplored areas**: None for Survey 1 scope. Complete evidence chain established.

## Key Decisions Made
- Confirmed root cause of visual drift is two-fold: upstream context saturation and downstream 280-char regex truncation.
- Formulated concrete 5-slot modular English design and specific actionable implementation handoffs for downstream agents.

## Artifact Index
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/survey_prompt.md — Full Survey Report
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/handoff.md — Handoff Report
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/progress.md — Progress and Heartbeat
- /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/DISPATCH.md — Dispatch Log
