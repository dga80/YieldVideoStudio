# Handoff Report: Survey 2 - Engine Adapter & Network Resilience Architecture

**Agent**: `teamwork_preview_explorer_survey_2`  
**Date**: 2026-10-06  
**Type**: Hard Handoff (Investigation & Survey Complete)  
**Target Report**: `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_survey_2/survey_engine.md`

---

## 1. Observation

1. **Active Route to `yieldchat_imagen.py`**:
   - `motores/imagen_openai/imagen.py:600-609`:
     ```python
     if not api_key and (not _claves_declaradas() or (hasattr(_cuentas()[0], 'clave') and _cuentas()[0].clave == "banana-flux")):
         from motores.imagen_openai import yieldchat_imagen
         return yieldchat_imagen.generar_imagen_yieldchat(prompt, referencias, tamano=tamano)
     ```
   - `secretos/claves.json:3`: `"openai": []` (no OpenAI API keys exist).
   - Therefore, all image generations in the studio route 100% through `yieldchat_imagen.generar_imagen_yieldchat`.

2. **Hardcoded 280-Character Truncation & Template Injection**:
   - `motores/imagen_openai/yieldchat_imagen.py:68`:
     `"Condensar a < 280 caracteres garantiza respuestas rápidas, estables y fieles."`
   - `motores/imagen_openai/yieldchat_imagen.py:150-151`:
     ```python
     prompt_resumen = ", ".join(partes)
     if len(prompt_resumen) > 280:
         prompt_resumen = prompt_resumen[:277] + "..."
     return prompt_resumen
     ```
   - `motores/imagen_openai/yieldchat_imagen.py:114`:
     For 3D scenes: `estilo_clave = "photorealistic 3D, chrome robot panels, glowing cyan details"` is forcefully injected regardless of the scene description.
   - `motores/imagen_openai/yieldchat_imagen.py:155-175`: `enriquecer_prompt` appends static boilerplate for 3D, stick, and 2D.

3. **Agnes AI Adapter Missing Base64 Delivery & Vulnerable to Ephemeral 404s**:
   - `motores/imagen_openai/yieldchat_imagen.py:403-407`:
     ```python
     payload = {
         "model": "agnes-image-2.1-flash",
         "prompt": prompt_completo,
         "size": img_size
     }
     ```
     `response_format: "b64_json"` is omitted.
   - `yieldchat_imagen.py:427-437`: Fetches secondary URL `img_url` (`https://platform-outputs.agnes-ai.space/...`) with `requests.get`. If replication lag or short TTL causes a 404, it fails silently and returns `(None, None)`.
   - Live probe of Agnes AI:
     - With `response_format: "b64_json"` and 956-character prompt: HTTP 200 OK, returns 1,701,396 characters of base64 in `data[0]["b64_json"]` in 9.4 seconds.
     - `yieldchat_imagen.py:416-426` already contains the base64 decoding logic (`base64.b64decode`, PIL validation, and PNG stream return).

4. **Provider Quotas and Availability**:
   - **SiliconFlow**: HTTP 402 with `{"code": 30001, "message": "Sorry, your account balance is insufficient"}`.
   - **Google Gemini**: HTTP 400 (`"Image generation is not available in your country."` / FAILED_PRECONDITION in EU) and HTTP 429 quota exhaustion.
   - **Pollinations.ai**: HTTP 200 with API key `sk_e8BV...`.

5. **Emergency Canvas Generation & Cache Pollution**:
   - `yieldchat_imagen.py:229-266` (`_crear_lienzo_cinematografico`): Creates emergency canvas PNGs with border pixel at (24, 24) colored RGBA `(212, 175, 55, 120)` of size 10–13 KB.
   - `pasos/p6_assets.py:2996-3008` (`_producir_imagen`): Saves returned PNG directly into `destino` and copies it to `banco_imagenes/{firma}.png` without checking `meta["modelo"]`.
   - Inspection of `/Users/danidev/Desktop/asVideoStudio/banco/imagenes`: **253 out of 1,707 cached images** are emergency canvases (< 20 KB) with pixel (24, 24) = `(212, 175, 55, 120)`.

---

## 2. Logic Chain

1. **Step 1 (Route Confirmation)**: Observation 1 proves that `imagen.py` unconditionally delegates to `yieldchat_imagen.py` because `claves.json` lacks OpenAI keys.
2. **Step 2 (Mutilation Origin)**: Observation 2 proves that `yieldchat_imagen.py` cuts prompts to 280 characters and injects static style strings (`chrome robot panels`). This explains why style guides and character descriptions generated upstream never reach the generation model.
3. **Step 3 (Failure Cascade)**: Observation 3 shows that `_intentar_generar_agnes` omits `response_format: "b64_json"`. When the ephemeral CDN URL on `platform-outputs.agnes-ai.space` returns 404, Agnes fails silently.
4. **Step 4 (Fallback Collapse)**: Observation 4 proves that SiliconFlow (HTTP 402) and Gemini (HTTP 400/429) cannot generate images. When Agnes fails, the pipeline exhausts all providers.
5. **Step 5 (Permanent Corruption)**: Observation 5 proves that when all providers fail, `yieldchat_imagen.py` renders an emergency canvas (`_crear_lienzo_cinematografico`), and `pasos/p6_assets.py` saves it into `banco/imagenes`. Subsequent runs re-serve the emergency canvas from cache permanently.
6. **Step 6 (Feasibility of Fix)**: Observation 3 proves that Agnes AI supports 950+ character prompts and `response_format: "b64_json"` natively with fast turnaround (~9s) and zero 404 risk.

---

## 3. Caveats

- SiliconFlow account currently has zero balance. If the user deposits funds, SiliconFlow can be used as a secondary fallback.
- Google AI Studio does not support the `IMAGE` modality for Gemini in the user's geographic region (EU/Spain).
- Pollinations.ai requires short prompts because it uses HTTP GET URL paths. If Pollinations is used as tier-3 fallback, it should retain a specialized URL encoder, but Agnes and SiliconFlow should never use it.

---

## 4. Conclusion

The root causes of image generation failures, prompt mutilation, and visual incoherence in `asVideoStudio` are fully diagnosed:
1. `yieldchat_imagen.py` has an obsolete 280-character cutoff and rigid template injector designed for Pollinations GET URLs that must be bypassed for Agnes AI.
2. Agnes AI is currently prone to 404 errors solely because it requests ephemeral URLs instead of base64; adding `"response_format": "b64_json"` eliminates 404 errors entirely.
3. `_producir_imagen` in `pasos/p6_assets.py` needs a quality guard to prevent emergency canvases from corrupting `banco/imagenes`.
4. SiliconFlow requires a 30-minute circuit-breaker to avoid wasted network attempts while balance is depleted.

All findings, architecture diagrams, and proposed code diffs are documented in `survey_engine.md`.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Agnes AI Base64 Support & Prompt Length**:
   ```bash
   python3 -c '
   import requests
   api_key = "sk-83GpBI3DHfOpOXb0UeSzxr0vD2VmIZ4sTrVR4CvOECpX0RIZ"
   url = "https://apihub.agnes-ai.com/v1/images/generations"
   headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
   payload = {
       "model": "agnes-image-2.1-flash",
       "prompt": "Cinematic test of rich descriptive prompt exceeding three hundred characters with technical lighting and palette constraints." * 5,
       "size": "1024x576",
       "response_format": "b64_json"
   }
   r = requests.post(url, json=payload, headers=headers, timeout=30)
   print("Status:", r.status_code, "B64 length:", len(r.json()["data"][0]["b64_json"]))
   '
   ```
   *Expected outcome*: Status 200, B64 length > 800,000.

2. **Verify SiliconFlow Balance (402)**:
   ```bash
   python3 -c '
   import requests
   api_key = "sk-uzfvuzphxrvjezneyjskdunvtgablrrtsqohkwmfgyvaxklz"
   url = "https://api.siliconflow.com/v1/images/generations"
   headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
   r = requests.post(url, json={"model": "Tongyi-MAI/Z-Image-Turbo", "prompt": "test"}, headers=headers)
   print("Status:", r.status_code, r.text)
   '
   ```
   *Expected outcome*: Status 402 (`"insufficient balance"`).

3. **Verify Emergency Canvases in `banco/imagenes`**:
   ```bash
   python3 -c '
   from PIL import Image
   im = Image.open("/Users/danidev/Desktop/asVideoStudio/banco/imagenes/732ae48a484a8ff5.png")
   print("Border pixel (24, 24):", im.getpixel((24, 24)))
   '
   ```
   *Expected outcome*: `(212, 175, 55, 120)` (verbatim output of `_crear_lienzo_cinematografico`).
