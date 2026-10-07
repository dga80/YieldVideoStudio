# Task Assignment: Survey 1 - Prompt Engineering & Text Encoder Architecture

You are teamwork_preview_explorer_survey_1.
Working directory: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1
Authoritative User Request: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md

## Objective
Survey the current prompt building pipeline in `asVideoStudio` with special focus on:
1. `pasos/p6_assets.py` and any related prompt generation modules.
2. Locate the 14 KB of Spanish meta-rules that saturate text encoder (CLIP/T5) context windows.
3. Locate phantom references (e.g., `Reference image 1`) and how references to character/style sheets are currently formatted.
4. Identify how prompts are passed to image engines (`motores/imagen_openai/yieldchat_imagen.py` or similar).
5. Recommend the concrete design for modular English prompts: `[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, `[NEGATIVE PROMPT]`.

## Requirements
- Read `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md` first.
- Write your comprehensive findings to `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/survey_prompt.md`.
- Write your `handoff.md` and update `progress.md`.
- Send your handoff message back to parent orchestrator via `send_message`.


## 2026-10-06T19:24:52Z
You are teamwork_preview_explorer_survey_1.
Your working directory is: /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1
Read /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md first.
Also read your task in /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/DISPATCH.md.

Investigate the prompt construction architecture in asVideoStudio:
1. Examine `pasos/p6_assets.py` and any other prompt-building scripts or templates.
2. Find the 14 KB of Spanish meta-rules saturating text encoder context windows.
3. Find phantom references (like 'Reference image 1') and how references are handled.
4. Trace how prompts flow to image generation engines.
5. Formulate recommendations for modular English prompts: [STYLE DNA], [SCENE/ACTION], [CHARACTER ANCHORS], [LIGHTING], [NEGATIVE PROMPT].

Write your full report to /Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/survey_prompt.md.
Write handoff.md and update progress.md in your working directory.
When done, send a message to orchestrator with your findings.
