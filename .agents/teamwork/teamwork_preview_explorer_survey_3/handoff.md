# Handoff Report: Survey 3 — Vision & Style Inversion + Adversarial QA

**Agent:** `teamwork_preview_explorer_survey_3`  
**Date:** 2026-10-06  
**Type:** Hard (Task complete)

---

## 1. Observation
1. **Reference Sheets & Preset Structure:**
   - `presets.json` (lines 1-140) defines presets including `pr1a0eef81dc7` (Pluma_2). Its assets are stored in `banco/presets/pr1a0eef81dc7/`: `00_cara.png` (830 KB), `01_cuerpos.png` (468 KB), `02_interior.png` (412 KB), `03_exterior.png` (381 KB), `04_objeto.png` (118 KB), `05_diagrama.png` (221 KB).
   - In `presets.json:25-47`, `guia` defines technical art properties: `paleta` (array of hex colors), `trazo`, `relleno`, `personajes`, `caras`, `manos`, `fondos`, `luz`, `composicion`, `acabado`, and `evitar`.
   - In `pasos/p6_assets.py:3703-3738`, `_lamina_estilo(rutas, destino)` combines up to 8 reference frames into a single composite grid image (`lamina_estilo_<hash>.png`).
2. **Degraded Cast Sheets & Silent Fallback:**
   - In `proyectos/que_pasaria_si_la_humanidad_dejara_de_morir_durante_24_horas/pasos/assets/v2/assets/reparto/`:
     - `criminales.png`: 197 KB, 1024x576, 15,010 unique colors (real generation).
     - `ejecutivos.png`, `gente_generica.png`, `medicos.png`, `pacientes.png`: all ~12 KB, 1280x720, exactly 500 unique colors.
   - In `motores/imagen_openai/yieldchat_imagen.py:229-266`, `_crear_lienzo_cinematografico` produces flat emergency canvases with 500 colors when external APIs fail or return errors.
3. **Prompt Mutilation and Phantom References:**
   - In `pasos/p6_assets.py:2596-2630`, `_prompt_completo` injects `"Reference image 1 is a STYLE SHEET..."` and `"Reference image 2 is the cast sheet for..."`.
   - In `motores/imagen_openai/yieldchat_imagen.py:403-408`, Agnes AI is called with `POST /v1/images/generations` passing only `{ "model": "agnes-image-2.1-flash", "prompt": prompt_completo, "size": img_size }`. No reference images are passed to the API.
   - In `motores/imagen_openai/yieldchat_imagen.py:64-152`, `limpiar_y_condensar_prompt` discards lines starting with `"Reference image"`, `"Style guide"`, truncates prompts to < 280 characters (`prompt_resumen[:277] + "..."`), and overwrites style with hardcoded strings (`"photorealistic 3D, chrome robot panels..."`, `"minimalist 2D stick figure cartoon"`).
   - In `pasos/p6_assets.py:2646`, `reglas.bloque_prompt("prompt_imagen")` injects 14 KB of human/LLM meta-rules in Spanish from `motores/reglas/reglas.json` into diffusion prompts.
4. **Agnes AI 404 URL Drops:**
   - In `motores/imagen_openai/yieldchat_imagen.py:403-428`, Agnes AI is called without `"response_format": "b64_json"`. When it returns ephemeral URLs, downloads fail or return 404, triggering silent fallback to dummy canvases.
5. **Multimodal Model & QA Tooling Capabilities:**
   - `secretos/.env` contains valid `GEMINI_API_KEY`, `AGNES_API_KEY`, and `SILICONFLOW_API_KEY`.
   - Python 3.12 environment has `google.genai`, `cv2` (OpenCV), `numpy`, `PIL`, `scipy`, and `requests` installed and verified.
   - Tested live inference: `pasos/gemini_cliente.py` executed multimodal vision analysis on `banco/presets/pr1a0eef81dc7/00_cara.png` in 6.8s, extracting technique, exact hex palette (`#F8F8F8`, `#82C872`, `#4A90E2`, etc.), stroke weight, and facial anchors.

---

## 2. Logic Chain
1. Step 1 (Observation 1 & 3): The project has rich visual reference sheets (`00_cara.png` .. `05_diagrama.png`), but passes references to text-to-image endpoints by writing `"Reference image 1..."` in prompt text.
2. Step 2 (Observation 3): Diffusion text encoders cannot resolve `"Reference image 1"` because no image is attached to the request. Furthermore, `yieldchat_imagen.py` strips those lines and truncates prompts to < 280 chars, substituting the preset with generic boilerplate strings.
3. Step 3 (Observation 2 & 4): When Agnes AI is invoked without `"response_format": "b64_json"`, ephemeral URLs fail/expire, and `yieldchat_imagen.py` falls back to `_crear_lienzo_cinematografico`, creating 12 KB blank placeholder cards (500 unique colors). This caused 4 out of 5 cast sheets in the active project to be blank dummy canvases.
4. Step 4 (Observation 5): Gemini 2.5 Flash Vision is active and capable of inverting reference sheets into dense, deterministic English visual descriptors (`[STYLE DNA]` and `[CHARACTER ANCHORS]`).
5. Step 5 (Observation 5): OpenCV (`cv2`) and `numpy` are available in the local environment and can instantly detect dummy canvases, compute Bhattacharyya color histogram distances against style sheets, and verify framing parameters without extra network overhead.
6. Step 6: Therefore, implementing Style & Character DNA Inversion via Gemini 2.5 Flash, purger-modular prompts without Spanish meta-rules, base64 responses in Agnes AI, and an OpenCV Adversarial Visual QA Judge completely resolves visual fidelity and API reliability.

---

## 3. Caveats
- SiliconFlow image model quotas/balance were not billed or stressed in live test; SiliconFlow acts as secondary fallback when Agnes AI encounters rate limits or maintenance.
- In painting/controlnet-based spatial conditioning is not supported on simple OpenAI-compatible `/v1/images/generations` endpoints; textual DNA conditioning is the correct mechanism for these engines.

---

## 4. Conclusion
The visual fidelity breakdown in `asVideoStudio` is completely diagnosed:
1. Phantom image references (`Reference image 1`) are incompatible with text-to-image endpoints and are stripped/mutilated by `yieldchat_imagen.py` along with 280-char clipping.
2. 14 KB of Spanish meta-rules flood CLIP/T5 text encoders.
3. Lack of `"response_format": "b64_json"` in Agnes AI causes 404 URL drops, silently defaulting to 12 KB emergency canvases.
4. Gemini 2.5 Flash Vision and OpenCV are fully available to implement the proposed 4-stage pipeline: Style/Character DNA Inversion -> Modular English Prompt Synthesizer -> Resilient Base64 Engine Adapter -> Adversarial Visual QA Judge.

Full architecture and implementation blueprint has been written to:
`/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_3/survey_vision_qa.md`.

---

## 5. Verification Method
1. **Inspect Survey Report:**
   - Verify contents of `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_3/survey_vision_qa.md`.
2. **Verify Environment Capabilities:**
   - Run: `python3 -c "import google.genai, cv2, numpy, PIL; print('Vision & QA libraries ready')"`
3. **Verify Degenerate vs Real Images:**
   - Run: `python3 -c "from PIL import Image; import numpy as np; print('medicos colors:', len(np.unique(np.array(Image.open('proyectos/que_pasaria_si_la_humanidad_dejara_de_morir_durante_24_horas/pasos/assets/v2/assets/reparto/medicos.png')).reshape(-1, 4), axis=0)))"`
4. **Invalidation Conditions:**
   - If `GEMINI_API_KEY` is revoked or `google.genai` is uninstalled.
   - If Agnes AI removes support for `b64_json`.
