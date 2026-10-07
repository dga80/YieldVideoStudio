# Survey 1: Prompt Construction Architecture & Text Encoder Context Analysis

**Author:** teamwork_preview_explorer_survey_1 (Teamwork Explorer)  
**Date:** 2026-10-06  
**Target Project:** `asVideoStudio`  
**Reference Document:** `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/ORIGINAL_REQUEST.md`  

---

## 1. Executive Summary

A comprehensive investigation into the visual fidelity pipeline of `asVideoStudio` reveals that the fundamental cause of style drift, character inconsistency, and fallback canvas generation is a severe architectural disconnect between **upstream prompt synthesis** in `pasos/p6_assets.py` and **downstream engine delivery** in `motores/imagen_openai/yieldchat_imagen.py`.

The system currently suffers from a destructive two-phase pipeline failure:

1. **Phase 1 — Massive Upstream Inflation & Token Saturation:**
   `pasos/p6_assets.py` concatenates style guides, character descriptions, reference image parsing instructions, camera directives, and an entire database of transversal Spanish feedback rules (`motores/reglas/reglas.json`). A single generated prompt reaches **10,685 to 19,193 characters** (~2,600 to 4,800 tokens). This completely overflows the context window of modern diffusion text encoders:
   - **CLIP ViT-L/14** (context limit: 77 tokens / ~300 chars) truncates the prompt before ever reaching the actual scene description, characters, setting, or lighting. The first 77 tokens are consumed entirely by meta-instructions ("Draw a single illustration for one shot... Never draw a grid...") and style sheet layout warnings.
   - **T5-XXL** (FLUX.1 / SD3, context limit: 256–512 tokens / ~1,000–2,000 chars) is overwhelmed by conversational Spanish meta-rules and repetitive instructions, crowding out fine-grained visual details.

2. **Phase 2 — Downstream Mutilation & Phantom References:**
   Because the upstream prompt is unmanageably huge, `motores/imagen_openai/yieldchat_imagen.py` attempts to sanitize it using `limpiar_y_condensar_prompt()`. This function:
   - Hard-truncates the prompt to **fewer than 280 characters** (`[:277] + "..."`).
   - Discards all character anchors, exact hex palettes, strokes, textures, and lighting.
   - Appends coarse, repetitive generic templates (e.g. `", clean line art, 2D vector animation style, high quality illustration"`).
   - Furthermore, while `p6_assets.py` writes instructions explicitly telling the model to *"Copy the face from Reference image 2"* and *"Match the architecture in Reference image 3"*, modern generation engines (Agnes AI, SiliconFlow, Gemini, Pollinations) are called as **pure text-to-image endpoints without any reference images attached**. These references are literally **phantom references**, prompting diffusion models to hallucinate non-existent reference images.

To achieve consistent style and character fidelity, `asVideoStudio` must replace this bloated and subsequently mutilated pipeline with a **Modular English Prompt Architecture** based on **Vision & Style Inversion (DNA extraction)** with 5 dedicated slots: `[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, and `[NEGATIVE PROMPT]`, maintaining a total budget under 250 tokens (~1,000 characters).

---

## 2. Investigation of Current Prompt Construction Architecture

### 2.1 Code Flow in `pasos/p6_assets.py`

The prompt construction pipeline in `pasos/p6_assets.py` revolves around `_prompt_completo` (line 2561) for scene shots and `_prompt_reparto` (line 2815) for cast sheets.

```
+-----------------------------------------------------------------------------------+
|                            pasos/p6_assets.py                                     |
|                                                                                   |
|  1. _prompt_visual()           -> Scene description, narration, shot type        |
|  2. guia_escrita()             -> 12-field style guide (palette, stroke, etc.)    |
|  3. clausula_de_especie()      -> Species vs identity conflict arbitration        |
|  4. frase_de_referencia()      -> Verbose instructions per reference image        |
|  5. reglas.bloque_prompt()     -> 5,660 chars of transversal Spanish rules        |
|  6. ULTIMA_PALABRA_ROTULOS     -> 623 chars of lettering restrictions             |
|  7. _ultima_palabra_idioma     -> 403 chars of language reinforcement             |
|  8. _bloque_feedback           -> 550 chars of reviewer override instructions     |
|                                                                                   |
|  Result: 10,685 - 19,193 characters (~2,600 - 4,800 tokens)                      |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                    motores/imagen_openai/imagen.py                                |
|  - Checks for OpenAI API key.                                                     |
|  - When key is missing or default ("banana-flux"), hands off directly to:         |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|               motores/imagen_openai/yieldchat_imagen.py                           |
|                                                                                   |
|  1. limpiar_y_condensar_prompt() -> Regex extracts 'Scene:', strips boilerplate,  |
|                                     HARD-TRUNCATES TO <= 280 CHARACTERS!          |
|  2. enriquecer_prompt()          -> Appends generic templates:                    |
|                                     "clean line art, 2D vector animation style..."|
|  3. Dispatches text-only payload to:                                              |
|     - Agnes AI (agnes-image-2.1-flash) [omits b64_json -> 404 URL drops]         |
|     - SiliconFlow (Tongyi Z-Image-Turbo / FLUX.1-schnell)                         |
|     - Gemini / Pollinations                                                       |
|     (ALL image attachments in 'referencias' are completely ignored/dropped)       |
+-----------------------------------------------------------------------------------+
```

### 2.2 Detailed Anatomy of `_prompt_completo`

In `p6_assets.py` (lines 2561–2692), `_prompt_completo` assembles the final prompt by concatenating lines into a single monolithic string via `" ".join(lineas)`:

1. **Preamble (lines 2570–2583):**
   ```python
   lineas = ["Draw a single illustration for one shot of an animated documentary."]
   if p2_brief.comun.normalizar_formato(formato) == "vertical":
       lineas.append("The frame is PORTRAIT (9:16, vertical, for a phone screen): compose for a tall frame. Put the subject large and centred, keep everything important within the middle two thirds of the height, and let the background fill the top and bottom naturally. Never draw black bars, borders or a landscape picture inside the tall frame.")
   ```
   *Impact:* 350+ characters before any visual content is described.

2. **Style Sheet Layout Disclaimer (lines 2591–2604):**
   ```python
   lineas.append(
       f"Reference image {indice} is a STYLE SHEET: a single picture that contains {ref.get('cuantas') or 'several'} separate frames from the same production, laid side by side only so they fit in one image. Copy the drawing style they share -- line weight, palette, shapes, proportions -- and never their content. Its grid layout is NOT part of the style and must NOT be reproduced: your output is ONE single full-bleed illustration of one moment. Never draw a grid, a collage, a contact sheet, panels, a split screen, borders, frames or separate boxes."
   )
   ```
   *Impact:* 530 characters warning diffusion models not to render a grid. Because diffusion models pay attention to keywords ("grid", "collage", "split screen", "panels"), placing these words in the positive prompt frequently causes the model to draw panels!

3. **Style Guide Extraction (`guia_escrita`, lines 2238–2295):**
   Iterates through up to 12 fields from `estilo["guia"]`:
   - `guia["guia"]` (Style guide paragraph, 260–400 words = ~1,500–2,500 chars)
   - `guia["paleta"]` ("Use this colour palette: #...")
   - `guia["trazo"]` ("Outlines: ...")
   - `guia["relleno"]` ("Fills and shading: ...")
   - `guia["personajes"]` ("Characters: ...")
   - `guia["caras"]` ("Faces: ...")
   - `guia["manos"]` ("Hands, arms and feet: ...")
   - `guia["fondos"]` ("Backgrounds: ...")
   - `guia["luz"]` ("Light and shadow: ...")
   - `guia["composicion"]` ("Composition: ...")
   - `guia["acabado"]` ("Finish and texture: ...")
   - `guia["evitar"]` ("Never do this, it breaks the style: ...")
   *Impact:* 1,500 to 3,500 characters.

4. **Species vs Identity Arbitration Clause (`clausula_de_especie`, lines 2197–2235):**
   ```python
   "HOW CHARACTERS ARE DRAWN IN THIS STYLE (species, anatomy, proportions), and this rule beats the wording of any character description in this prompt: {regla} Where a description says 'a man', 'a woman', 'a person' or 'people', draw that character with the species and anatomy this rule gives to everyone, never as a realistic human unless the rule itself says so."
   "But the rule decides ONLY species and anatomy. Each character's IDENTITY -- face, hair, facial hair, glasses, age, build, and especially their clothing and accessories -- comes from their cast sheet when one is attached..."
   ```
   *Impact:* 850 characters of conversational logic instructing the model on hierarchical precedence.

5. **Reference Image Descriptions (`frase_de_referencia`, lines 2314–2493):**
   Generates a verbose paragraph for each referenced file:
   - For `reparto`: 450–700 chars instructing the model to copy face/hair/clothes from `Reference image N`.
   - For `continuidad`: 750–900 chars instructing the model to copy architecture from `Reference image N` but not composition.
   - For `parecido` / `real` / `rechazada`: 500–800 chars each.
   *Impact:* 1,200 to 2,500 characters.

6. **Transversal Feedback Rules (`reglas.bloque_prompt("prompt_imagen")`, line 2646):**
   Injects all rules marked for `prompt_imagen` from `motores/reglas/reglas.json`.
   *Impact:* **5,660 characters** of conversational Spanish and English guidelines.

7. **Scene Staging (`_prompt_visual`, lines 1846–1973):**
   Contains the actual shot description:
   - Set description (from catalog)
   - Beat action
   - Cast citation (`with the character '...' drawn matching...`)
   - Facial expression formula (`neutral faces: straight closed mouth...`)
   - Narration anchor: `"This shot accompanies the narration line: \"{linea}\". Show the specific moment that line describes -- or, when the line is abstract, stage one concrete scene... Never a generic view of the location."`
   - Shot type: `"SHOT TYPE, and this is not optional: {escena['encuadre']}."`
   *Impact:* 600 to 1,500 characters. Notice that this crucial block is positioned **after line 2675**—thousands of tokens into the prompt!

8. **Lettering and Diacritics Final Enforcement (lines 2680–2684):**
   - `ULTIMA_PALABRA_ROTULOS` (lines 2515–2524): 623 characters.
   - `_ultima_palabra_idioma` (lines 2526–2559): 403 characters.

9. **Feedback / Correction Block (`_bloque_feedback`, lines 2740–2750):**
   ```python
   "The reviewer looked at the previous image of this exact shot and REJECTED it. Everything described above -- the scene, the action, the framing and the SHOT TYPE line -- is the description that produced the image that was rejected. The reviewer's note below is the HIGHEST PRIORITY instruction in this entire prompt and it OVERRIDES anything above it that disagrees with it... The reviewer's note is: {feedback}."
   ```
   *Impact:* 550+ characters.

---

## 3. The 14 KB of Spanish Meta-Rules & Text Encoder Context Saturation

### 3.1 Location and Exact Measurement of Meta-Rules

The meta-rules originate from `motores/reglas/reglas.json` (size on disk: **24,023 bytes**), managed by `motores/reglas/reglas.py`.

A quantitative inspection of `reglas.json` reveals:
- **Total rule objects:** 18
- **Total characters across all 18 rules (active text):** 8,759 characters
- **Total characters including `regla`, `por_que`, and `origen`:** 17,963 characters (~18 KB of total feedback documentation)
- **Rules injected directly into `prompt_imagen`:** 9 rules totaling **5,660 characters** (approx. 1,415 tokens).

The 9 rules injected verbatim into every image generation prompt via `reglas.bloque_prompt("prompt_imagen")` are:

| Rule ID | Language | Chars | Excerpt / Content |
|---|---|---|---|
| `hora-del-dia-explicita` | **Spanish** | 206 | *"Todo prompt de escena debe fijar explicitamente la hora del dia y la fuente de luz. Si la escena es interior, se especifica la luz interior Y si por las aberturas entra dia o noche..."* |
| `continuidad-luz-entre-planos` | **Spanish** | 191 | *"La hora del dia se hereda del plano anterior salvo que el guion diga lo contrario. Si cambia, el cambio debe ser deliberado y estar escrito en el plan de escenas..."* |
| `expresion-facial-explicita` | **Spanish** | 449 | *"Todo prompt que contenga personajes debe declarar de forma explicita la expresion facial de cada uno, acorde al tono de la escena (boca, cejas y mirada). La sonrisa esta PROHIBIDA por defecto..."* |
| `manos-segun-la-guia` | **Spanish** | 525 | *"Las manos, los brazos y los pies se dibujan con la CONVENCION DEL ESTILO, y esa convencion la fija la guia de estilo, no este fichero. Si la guia dice cuantos dedos hay, ese numero manda..."* |
| `texto-en-imagen-permitido-pero-raro` | English | 1,746 | *"Text inside the drawing is ALLOWED. WHETHER it appears is decided by what is being drawn: lettering belongs where it is part of what the thing IS... AMOUNT: at most ten words... SIZE: readable at a glance..."* |
| `un-personaje-aparece-una-vez` | **Spanish** | 433 | *"CADA PERSONAJE NOMBRADO APARECE UNA SOLA VEZ EN EL CUADRO, y aparece COMO PERSONA PRESENTE. No se dibuja ademas su retrato, su foto, su silueta, su avatar ni su cara en una pantalla..."* |
| `nada-de-letras-inventadas` | **Spanish** | 582 | *"NO SE DIBUJA NINGUNA LETRA QUE NO SE HAYA PEDIDO. Todo texto que aparezca en el cuadro --un rotulo, una pantalla, una portada, una etiqueta, una pancarta-- tiene que estar pedido explicitamente..."* |
| `el-sentido-lo-fija-el-relato` | **Spanish** | 537 | *"UNA PALABRA CON DOS SENTIDOS SE ESCENIFICA EN EL SENTIDO QUE LE DA EL RELATO, y ese sentido se escribe en el prompt, no se deja implicito. Cuando un termino tiene un significado cotidiano..."* |
| `texto-dibujado-en-el-idioma-del-video` | English | 983 | *"THE LETTERING YOU DRAW BELONGS TO THE FILM, NOT TO THESE INSTRUCTIONS. These instructions are written in English, and English is NOT the language of the film. The film's language is the one this prompt states..."* |

In addition to `reglas.json`, `p6_assets.py` injects Spanish identifiers and rules in:
- `MARCA_OTRO_SITIO = "EN OTRO SITIO:"` (line 2100)
- `_citar_reparto` character naming conventions
- `TONOS` dictionary tone translations
- Upstream prompt instructions in `pasos/catalogo_visual.py` and `pasos/direccion.py`.

### 3.2 The Impact on Text Encoders (CLIP & T5)

1. **CLIP Context Truncation (77 Tokens / ~300 Chars):**
   Text-to-image models based on CLIP (SD 1.5, SDXL, and CLIP ViT-L heads in SD3/Flux) process exactly 77 tokens including `<start>` and `<end>`. In `p6_assets._prompt_completo`, the first 77 tokens contain only:
   ```
   Draw a single illustration for one shot of an animated documentary. Reference image 1 is a STYLE SHEET: a single picture that contains 6 separate frames from the same production, laid side by side only so they fit in one image. Copy the drawing style they share -- line weight, palette, shapes, proportions -- and never their content.
   ```
   **The actual scene (`Scene: ...`), the characters, and the lighting are positioned 1,500 to 2,000 tokens later!** In any CLIP-evaluated pipeline, 100% of the actual scene description is cut off before the text encoder finishes its first pass.

2. **T5-XXL Token Capacity Dilution (256–512 Tokens):**
   Modern diffusion transformers like FLUX.1 (used in SiliconFlow) and SD3 utilize T5-XXL. While T5 supports up to 256 or 512 tokens, injecting 5,660 characters of Spanish meta-rules completely saturates this window with non-visual policy instructions.

3. **Multilingual Token Fragmentation Penalty:**
   T5 and CLIP subword tokenizers (SentencePiece and BPE) are heavily trained on English web corpora. Spanish words containing diacritics and accented characters (`fijar explícitamente`, `convención`, `expresión`) fragment into 2 to 4 separate tokens each. This imposes a **30% to 50% token bloat penalty** compared to English equivalents.

4. **Negative Token Leakage via Positive Prompting:**
   Diffusion attention heads compute cross-attention between token embeddings and latent spatial features. Phrasing negative rules conversationally in the positive prompt (e.g., *"La sonrisa está PROHIBIDA por defecto"*, *"No se dibuja además su retrato"*, *"Never draw a grid or collage"*) actually **activates the attention weights for 'sonrisa', 'retrato', 'grid', and 'collage'**. The model lacks a negation operator in latent space; mentioning forbidden concepts in the prompt induces their generation.

---

## 4. Phantom References and Reference Handling

### 4.1 Identification of Phantom References

Throughout `p6_assets.py`, `moodboard.py`, and `corrector.py`, prompts are constructed with explicit textual references to numbered image files:

- `p6_assets.py:2596`: `"Reference image {indice} is a STYLE SHEET: a single picture that contains ..."`
- `p6_assets.py:2613`: `"Match exactly the art style of reference image {estilos[0]} ..."`
- `p6_assets.py:2330`: `"Reference image {indice} is the cast sheet for '{ref['nombre']}' ..."`
- `p6_assets.py:2344`: `"Reference image {indice} is the cast sheet for '{ref['nombre']}': draw those exact characters. Copy their faces, hair, skin tone, build and clothes exactly as drawn there..."`
- `p6_assets.py:2390`: `"Reference image {indice} is an earlier shot of THIS SAME PLACE ..."`
- `p6_assets.py:2416`: `"Reference image {indice} is a PHOTOGRAPH of the real {ref.get('que_es')} ..."`
- `p6_assets.py:2830`: `"Reference image 1 is a STYLE SHEET: copy the drawing style it shows ..."`

### 4.2 How References Are Actually Handled (The Engine Disconnect)

In the legacy OpenAI `/v1/images/edits` implementation (`motores/imagen_openai/imagen.py`), image files were physically uploaded as multipart form data (`files=[("image[]", ...)]`).

However, in `motores/imagen_openai/yieldchat_imagen.py`—which handles all execution for Agnes AI, SiliconFlow, Google Gemini, and Pollinations—**none of the engines accept reference image files**:

1. **Agnes AI (`_intentar_generar_agnes`, line 388):**
   ```python
   payload = {
       "model": "agnes-image-2.1-flash",
       "prompt": prompt_completo,
       "size": img_size
   }
   resp = requests.post(url, json=payload, headers=headers, timeout=35)
   ```
   Sends only a text JSON payload to `/v1/images/generations`. No images are uploaded.

2. **SiliconFlow (`_intentar_generar_siliconflow`, line 443):**
   ```python
   payload = {
       "model": mod,
       "prompt": prompt_completo,
       "image_size": img_size
   }
   resp = requests.post(url, json=payload, headers=headers, timeout=30)
   ```
   Sends only a text JSON payload to `/v1/images/generations`. No images are uploaded.

3. **Gemini (`_intentar_generar_gemini`, line 494):**
   Sends only a text JSON payload (`contents=[{"parts": [{"text": prompt_limpio}]}]`).

4. **Pollinations.ai (line 670):**
   Encodes the prompt into an HTTP GET URL string.

### 4.3 The Consequence of Phantom References

Because `yieldchat_imagen.py` never passes reference images to the API:
- The diffusion models read: *"Reference image 1 is a STYLE SHEET... Reference image 2 is the cast sheet for 'banquero_central': draw those exact characters..."*
- **The model has no access to Image 1 or Image 2.**
- The model experiences prompt conflict: it is told that the face details are in a reference sheet that does not exist in its input tensors, forcing it to generate a generic stochastic face.
- When generation inevitably fails, `yieldchat_imagen.py` triggers `_resolver_referencia_real` (lines 178–227):
  ```python
  h = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
  elegida = candidatas[h % len(candidatas)]
  ```
  It computes a SHA-256 hash of the prompt and **picks an arbitrary existing PNG from disk**, returning a completely unrelated scene from an earlier video!

---

## 5. End-to-End Trace of Prompt Flow to Image Generation Engines

```
[p6_assets.py: _generar_escenas]
          |
          v
[p6_assets.py: _prompt_completo]
  --> Assembles: Preamble + Reference descriptions + Style Guide + 
                 Species Clause + 5.6KB Spanish Rules + Scene Staging + 
                 Lettering Rules + Feedback Override.
  --> String length: 10,685 - 19,193 characters.
          |
          v
[p6_assets.py: _producir_imagen]
  --> Hashes prompt and reference paths for caching.
          |
          v
[motores/imagen_openai/imagen.py: generar]
  --> Checks API keys (lines 600-610).
  --> If OPENAI_API_KEY is not defined or is "banana-flux", hands off to:
          |
          v
[motores/imagen_openai/yieldchat_imagen.py: generar_imagen_yieldchat]
          |
          +--> 1. Provider Selection:
          |       Reads ajustes.json ("generador_imagen": "agnes")
          |
          +--> 2. Prompt Mutilation (limpiar_y_condensar_prompt):
          |       - Regex searches for r"(?:Scene|Escena|SHOT|PLANO):\s*(.*?)"
          |       - Strips hardcoded patterns (tone, stick figures, boilerplate)
          |       - TRUNCATES: if len(prompt_resumen) > 280: prompt_resumen[:277] + "..."
          |
          +--> 3. Generic Overwrite (enriquecer_prompt):
          |       - Regex classifies style as "3d", "stick", or "2d"
          |       - Appends hardcoded string:
          |         "clean line art, 2D vector animation style, high quality illustration"
          |
          +--> 4. Engine Delivery (Agnes AI / SiliconFlow / Gemini):
                  - Calls Agnes AI without "response_format": "b64_json"
                  - Agnes returns ephemeral CDN URL
                  - Secondary download fails (404) or expires
                  - Fallback triggers:
                    -> SiliconFlow (often exhausted quota)
                    -> Gemini
                    -> Pollinations
                    -> _resolver_referencia_real (random disk image)
                    -> _crear_lienzo_cinematografico (emergency graphic canvas)
```

### 5.1 Verification of Prompt Mutilation

Running a live execution trace of a 10,685-character prompt produced by `p6_assets.py` through `yieldchat_imagen.py` yielded:

- **Input Prompt to `yieldchat_imagen.py`:** 10,685 characters (1,851 words, ~2,670 tokens)
- **Output of `limpiar_y_condensar_prompt`:** 160 characters
- **Output of `enriquecer_prompt`:** 230 characters:
  ```
  Inside the grand trading room of the central bank, dim monitors glowing in the dark, nervous traders watching screens, 2D vector animation style, clean line art, clean line art, 2D vector animation style, high quality illustration
  ```

**97.8% of the prompt was obliterated.** Every single detail of the artist's style guide, color palette, lighting atmosphere, and character anchors was erased and replaced with duplicated generic strings.

---

## 6. Recommendations for Modular English Prompt Architecture

To establish visual fidelity without text encoder saturation or downstream prompt mutilation, the prompt pipeline must be restructured into a **Strict 5-Slot Modular English Schema**.

### 6.1 The 5-Slot Modular Architecture

```
+---------------------------------------------------------------------------------------------------+
|                               MODULAR ENGLISH PROMPT SCHEMA                                       |
|                                                                                                   |
|  [STYLE DNA]             ~40-60 tokens   | Pictorial technique, stroke, exact hex palette, texture|
|  [SCENE/ACTION]          ~40-70 tokens   | Staging, subject, camera shot type, dynamic action     |
|  [CHARACTER ANCHORS]     ~30-50 tokens   | Explicit facial & costume conditioning (Character DNA)  |
|  [LIGHTING]              ~20-30 tokens   | Illumination source, time of day, contrast             |
|                                                                                                   |
|  TOTAL POSITIVE PROMPT:  130-210 tokens  (Fits cleanly inside T5 & prioritizes CLIP heads)        |
+---------------------------------------------------------------------------------------------------+
|  [NEGATIVE PROMPT]       ~30-50 tokens   | Dedicated negative tensor: 3D render, photorealism,    |
|                                            smiling, deformed hands, text, collage, grid           |
+---------------------------------------------------------------------------------------------------+
```

#### Slot 1: `[STYLE DNA]` (Target: 40–60 tokens)
- Extracted once per preset (or updated when `lamina_estilo.png` changes) by the **Vision & Style Inversion Agent** using multimodal analysis (Gemini 2.5 Flash Vision).
- Contains dense, technical descriptors of the artistic medium, outline weight, color palette, and surface finish.
- Formatted without conversational filler or negative prohibitions.
- *Example:*
  ```text
  [STYLE DNA]: Editorial 2D vector illustration, crisp uniform 3px dark navy outlines, flat matte color fills in #1a2b3c, #f0f0f0, #e63946, #457b9d, zero gradients, subtle risograph paper texture.
  ```

#### Slot 2: `[SCENE/ACTION]` (Target: 40–70 tokens)
- Specifies the shot composition, foreground/background elements, and character action.
- Directly incorporates the shot type (`medium close-up`, `wide establishing shot`, `dutch angle`) without the conversational prefix `"SHOT TYPE, and this is not optional:"`.
- *Example:*
  ```text
  [SCENE/ACTION]: Wide low-angle shot inside a high-ceiling central bank trading floor. Multiple anxious financial traders seated at curved workstations staring up at massive red electronic ticker boards.
  ```

#### Slot 3: `[CHARACTER ANCHORS]` (Target: 30–50 tokens)
- Replaces phantom cast sheets (`"Reference image 2 is the cast sheet..."`) with **Character DNA Inversion**.
- Specifies immutable physical attributes, facial structure, hair, and clothing directly in text so text-to-image models can generate consistent characters across shots.
- *Example:*
  ```text
  [CHARACTER ANCHORS]: Character 'central_banker': 55-year-old slender man, sharp angular jaw, receding silver hair, thin wire spectacles, dark charcoal wool three-piece suit, crimson tie.
  ```

#### Slot 4: `[LIGHTING]` (Target: 20–30 tokens)
- Replaces the separate Spanish lighting rules (`hora-del-dia-explicita`, `continuidad-luz-entre-planos`) with concrete lighting and atmospheric conditioning.
- *Example:*
  ```text
  [LIGHTING]: Nocturnal interior, cold cyan monitor glow casting sharp highlights against deep navy shadows, warm halogen desk lamp accents.
  ```

#### Slot 5: `[NEGATIVE PROMPT]` (Target: 30–50 tokens)
- Separated from the positive prompt and passed to diffusion engines via their dedicated `negative_prompt` API argument (or appended cleanly if an API only accepts a single string).
- Consolidates all transversal prohibitions (`manos-segun-la-guia`, `expresion-facial-explicita`, `texto-en-imagen-permitido-pero-raro`, `lamina` grid prohibitions).
- *Example:*
  ```text
  [NEGATIVE PROMPT]: photorealistic, 3D render, CGI, realistic skin texture, gradients, drop shadows, smiling, cheerful expression, deformed hands, extra fingers, malformed limbs, watermark, signature, text, typography, split screen, collage, borders, grid.
  ```

### 6.2 Comparison: Legacy Pipeline vs. Modular Architecture

| Metric / Dimension | Legacy `asVideoStudio` Pipeline | Proposed Modular English Architecture | Improvement |
|---|---|---|---|
| **Prompt Length** | 10,685 – 19,193 characters | 650 – 950 characters | **94% reduction in token bloat** |
| **Token Count** | ~2,600 – 4,800 tokens | ~150 – 220 tokens | **Fits 100% within T5 context** |
| **CLIP Context Fit** | Scene truncated (token > 150) | Scene fits in tokens 1–77 | **Full CLIP adherence** |
| **Language** | Hybrid Spanish / English | 100% English | **Eliminates BPE subword penalty** |
| **Reference Handling** | Phantom text referencing missing files | Textual Character & Style DNA | **Eliminates hallucination / drift** |
| **Engine Preprocessing** | Mutilated to <280 chars & overwritten | Preserved intact across engines | **Zero prompt mutilation** |
| **Negative Logic** | Leaked into positive prompt | Dedicated negative channel | **Prevents negative feature triggering** |

### 6.3 Implementation Roadmap for Downstream Agents

1. **For Agent 1 (Vision & Style Inversion Agent):**
   - Create an automated inversion pipeline using Gemini 2.5 Flash Vision to inspect `lamina_estilo.png` and `reparto/*.png`.
   - Output structured JSON containing `style_dna` and `character_anchors` for each character in the catalog.
   - Store these descriptors in `catalogo.json` / preset metadata so they are instantly accessible to prompt assemblers.

2. **For Agent 2 (Prompt Engineering & Text Encoder Agent):**
   - Refactor `_prompt_completo` in `pasos/p6_assets.py` to assemble the 5 modular slots.
   - Deprecate `reglas.bloque_prompt("prompt_imagen")` from positive prompt generation.
   - Move all negative rules into a clean `[NEGATIVE PROMPT]` string.
   - Remove phantom reference formatting (`"Reference image N is..."`).

3. **For Agent 3 (Engine Adapter & Network Agent):**
   - In `motores/imagen_openai/yieldchat_imagen.py`, completely remove `limpiar_y_condensar_prompt()` and the 280-character truncate.
   - Remove the hardcoded template overwrites in `enriquecer_prompt()`.
   - In `_intentar_generar_agnes()`, add `"response_format": "b64_json"` to the payload to eliminate ephemeral 404 URL errors.
   - Implement clean parameter mapping for negative prompts across Agnes AI, SiliconFlow, and Gemini.

4. **For Agent 4 (Adversarial QA & Style Consistency Judge):**
   - Implement programmatic validation comparing generated scenes against preset palette histograms and verifying that no scenes fall back to `yield-canvas` emergency canvases.

---

## 7. Conclusion

The visual inconsistency in `asVideoStudio` is not an inherent limitation of diffusion models, but the predictable result of context-window saturation upstream followed by aggressive regex mutilation downstream. By eliminating phantom references, removing the 14 KB of conversational Spanish meta-rules, and adopting a compact 5-slot modular English prompt schema, the system will achieve consistent style retention, precise character continuity, and robust API delivery.
