# Handoff Report: Survey 1 - Prompt Engineering & Text Encoder Architecture

**Agent:** `teamwork_preview_explorer_survey_1`  
**Handoff Type:** Hard (Task complete)  
**Date:** 2026-10-06  
**Primary Deliverable:** `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/survey_prompt.md`  

---

## 1. Observation

1. **Massive Upstream Prompt Concatenation (`pasos/p6_assets.py`):**
   - In `pasos/p6_assets.py:2561` (`_prompt_completo`), prompts are formed by concatenating preamble lines (2570–2583), style sheet layout disclaimers (2591–2604), 12-field style guide (`guia_escrita`, 2238–2295), species hierarchy clauses (`clausula_de_especie`, 2197–2235), reference image descriptions (`frase_de_referencia`, 2314–2493), transversal rules (`reglas.bloque_prompt("prompt_imagen")`, line 2646), scene staging (`_prompt_visual`, 1846–1973), lettering enforcement (`ULTIMA_PALABRA_ROTULOS`, 2515–2524), language enforcement (2526–2559), and feedback overrides (`_bloque_feedback`, 2740–2750).
   - Direct measurement via Python execution reveals a single scene prompt produced by `_prompt_completo` is **10,685 characters (1,851 words, ~2,670 tokens)**, scaling up to **19,193 characters** in production (as confirmed in `p6_assets.py:2380` and `pasos/redactor.py:20`: *"de 19.193 caracteres de prompt, 236 --el 1,2 %-- describian el plano"*).

2. **Transversal Spanish Meta-Rules in `motores/reglas/reglas.json`:**
   - File size on disk: **24,023 bytes** across 18 rules.
   - Total text in `reglas.json` (rules + rationale + origin metadata): **17,963 characters**.
   - Active rule bodies: **8,759 characters**.
   - 9 rules are classified under `ambito: "prompt_imagen"` and injected directly via `reglas.bloque_prompt("prompt_imagen")` (line 2646), adding **5,660 characters** (~1,415 tokens) into every prompt.
   - 7 of these 9 rules are conversational Spanish text (e.g. `hora-del-dia-explicita`, `continuidad-luz-entre-planos`, `expresion-facial-explicita`, `manos-segun-la-guia`, `un-personaje-aparece-una-vez`, `nada-de-letras-inventadas`, `el-sentido-lo-fija-el-relato`).

3. **Phantom Reference Image Directives:**
   - `p6_assets.py` generates textual references to numbered images:
     - Line 2596: `"Reference image {indice} is a STYLE SHEET..."`
     - Line 2330: `"Reference image {indice} is the cast sheet for '{ref['nombre']}'..."`
     - Line 2390: `"Reference image {indice} is an earlier shot of THIS SAME PLACE..."`
     - Line 2830: `"Reference image 1 is a STYLE SHEET..."`
   - However, in `motores/imagen_openai/yieldchat_imagen.py`:
     - Line 403 (`_intentar_generar_agnes`): Sends JSON payload `{"model": "agnes-image-2.1-flash", "prompt": prompt_completo, "size": img_size}`. **Zero image attachments are sent.**
     - Line 466 (`_intentar_generar_siliconflow`): Sends JSON payload `{"model": mod, "prompt": prompt_completo, "image_size": img_size}`. **Zero image attachments are sent.**
     - Line 517 (`_intentar_generar_gemini`): Sends text JSON payload. **Zero image attachments are sent.**
     - The models are text-to-image endpoints receiving orders to copy from non-existent images.

4. **Downstream Prompt Mutilation in `motores/imagen_openai/yieldchat_imagen.py`:**
   - In `yieldchat_imagen.py:64` (`limpiar_y_condensar_prompt`), incoming prompts are regex-parsed and **hard-truncated**:
     ```python
     if len(prompt_resumen) > 280:
         prompt_resumen = prompt_resumen[:277] + "..."
     ```
   - In `yieldchat_imagen.py:155` (`enriquecer_prompt`), the truncated text is appended with coarse hardcoded strings (e.g. `", clean line art, 2D vector animation style, high quality illustration"`).
   - In live testing, the 10,685-character prompt was reduced to **230 characters**, discarding 97.8% of prompt information including all palettes, textures, character anchors, and lighting.

5. **Missing Base64 in Agnes AI Delivery:**
   - In `yieldchat_imagen.py:403`, the Agnes AI payload omits `"response_format": "b64_json"`.
   - Agnes AI returns ephemeral CDN URLs that trigger HTTP 404 on subsequent downloads, causing the system to fall back to random image adoption (`_resolver_referencia_real`, hashing the prompt to select an unrelated PNG from disk) or emergency canvas cards (`_crear_lienzo_cinematografico`).

---

## 2. Logic Chain

1. From **Observation 1**, `p6_assets.py` builds prompts exceeding 10,000–19,000 characters (~2,600–4,800 tokens).
2. Given that standard diffusion text encoders have strict context windows (CLIP: 77 tokens; T5-XXL: 256–512 tokens), the primary scene description (`Scene: ...`), characters, and lighting (positioned after token 1,500) are completely cut off in CLIP and heavily diluted in T5.
3. From **Observation 2**, the 5,660 characters of conversational Spanish rules from `reglas.json` consume over 1,400 tokens with high-level negative instructions. In latent diffusion, conversational negatives like *"La sonrisa está PROHIBIDA"* in the positive prompt activate attention weights for prohibited tokens, inducing errors rather than preventing them, while Spanish BPE tokenization increases token overhead by 30–50%.
4. From **Observation 3**, the prompts continuously command the model to inspect `Reference image 1`, `Reference image 2`, etc., yet `yieldchat_imagen.py` dispatches only text payloads to Agnes AI and SiliconFlow. The diffusion models receive zero image inputs, causing severe hallucinations and stochastic drift.
5. From **Observation 4**, `yieldchat_imagen.py` attempts to remedy the prompt length by violently cutting it to under 280 characters and appending generic boilerplate. This erases the unique style identity of the preset.
6. From **Observation 5**, omitting `"response_format": "b64_json"` in Agnes AI results in ephemeral URL download failures (404), triggering fallbacks to unrelated disk images or emergency canvases.
7. Therefore, to achieve visual fidelity and stability, the system must:
   - Replace phantom image references with **Vision Inversion (Textual Style & Character DNA)**.
   - Purge the Spanish meta-rules from positive prompt generation.
   - Structure a **Modular English Prompt** with 5 explicit slots (`[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, `[NEGATIVE PROMPT]`) under 250 tokens total.
   - Remove the 280-character truncate and enforce `"response_format": "b64_json"` in `yieldchat_imagen.py`.

---

## 3. Caveats

- **Legacy OpenAI Edits:** The older, non-default pipeline in `motores/imagen_openai/imagen.py` targeting OpenAI `/v1/images/edits` does support multipart file uploads. However, as configured in `ajustes.json: "generador_imagen": "agnes"`, the system routes to `yieldchat_imagen.py`.
- **Model-Specific Token Capacities:** While FLUX.1 supports 512 tokens on T5-XXL, Agnes AI (`agnes-image-2.1-flash`) has proprietary token limits that are not documented in public API headers. A strict budget under 250 tokens ensures compatibility across all target providers.

---

## 4. Conclusion

The visual failure and stylistic inconsistency in `asVideoStudio` are caused by context window saturation upstream and aggressive regex truncation downstream. The solution is:
1. Deprecate conversational Spanish rules and phantom reference text from `p6_assets.py`.
2. Adopt a compact 5-slot Modular English Prompt architecture:
   - `[STYLE DNA]` (~40–60 tokens): Extracted via multimodal vision from `lamina_estilo.png`.
   - `[SCENE/ACTION]` (~40–70 tokens): Framing, setting, subjects, and action.
   - `[CHARACTER ANCHORS]` (~30–50 tokens): Explicit textual visual descriptors for characters.
   - `[LIGHTING]` (~20–30 tokens): Illumination source and atmosphere.
   - `[NEGATIVE PROMPT]` (~30–50 tokens): Dedicated negative channel isolating all prohibitions.
3. Remove prompt truncation in `yieldchat_imagen.py` and enforce `"response_format": "b64_json"` on Agnes AI.

---

## 5. Verification Method

1. **Inspect Report:**
   Read `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_1/survey_prompt.md`.
2. **Reproduce Prompt Bloat & Truncation:**
   Run the following terminal command from repository root:
   ```bash
   python3 -c '
   import sys; sys.path.insert(0, "pasos"); sys.path.insert(0, "motores/imagen_openai")
   import p6_assets, yieldchat_imagen
   escena = {"id": "S1", "narracion": "Test", "encuadre": "wide shot", "prompt": "Test scene", "personajes": [], "luz": "day", "set": "room"}
   p = p6_assets._prompt_completo(escena, [], {"guia": {"guia": "Style"}}, idioma="es")
   print("p6 length:", len(p))
   c = yieldchat_imagen.limpiar_y_condensar_prompt(p)
   print("yieldchat length:", len(c))
   assert len(p) > 5000 and len(c) <= 280
   print("Verified prompt saturation and mutilation.")
   '
   ```
3. **Invalidation Conditions:**
   This analysis is invalidated if `yieldchat_imagen.py` passes image tensors/files directly to Agnes AI or SiliconFlow, or if `reglas.bloque_prompt("prompt_imagen")` is proved not to be called in `p6_assets._prompt_completo`.
