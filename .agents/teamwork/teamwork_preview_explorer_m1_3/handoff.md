# Handoff Report: Fallback Mechanisms, Heuristics & Verification Strategy (Milestone 1)

**Agent**: `teamwork_preview_explorer_m1_3`  
**Working Directory**: `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_3`  
**Handoff Type**: Hard (Investigation complete, actionable architecture and test suite delivered)  

---

## 1. Observation

1. **Preset Guia Field Richness (`presets.json:25-77`)**:
   `presets.json` contains 4 presets (`pr1a0eef81dc7`, `pr1a0f81fbf25`, `pr1a0f91a4e44`, `pr1a10889874e`) with dense, structured English styling fields under `datos.estilo.guia`:
   - `guia`: Narrative visual specification paragraph in English.
   - `paleta`: List of 8 hex colors (e.g. `['#ffffff', '#000000', '#7cc47c', '#3a86ff', '#ffb703', '#fb8500', '#d90429', '#2b2d42']` for Pluma_2).
   - `trazo`: Outline thickness and style (e.g. `"Outlines are uniform solid black lines, approximately 3 to 4 pixels thick..."`).
   - `relleno`: Fill characteristics (e.g. `"Surfaces are filled with flat solid colors with zero gradients..."`).
   - `luz`: Lighting model (e.g. `"Lighting is completely flat and ambient with no light source direction..."`).
   - `acabado`: Medium and render quality (e.g. `"Clean digital vector look with minimal hand-drawn marker imperfection..."` or `"The final render is a photorealistic 3D image..."`).
   - `evitar`: Negative constraints (e.g. `['no skin gradients', 'no cast shadows', 'no eye highlights', ...]` or string representations).

2. **Emergency Canvas Generation (`motores/imagen_openai/yieldchat_imagen.py:261`)**:
   `yieldchat_imagen.py:261` constructs emergency placeholder canvases with a distinctive gold border:
   ```python
   draw.rectangle([(24, 24), (width - 24, height - 24)], outline=(212, 175, 55, 120), width=2)
   ```
   These images are typically 12 KB to 16 KB PNG files with virtually zero color entropy.

3. **Existing Emergency Canvases in Repository Assets (`proyectos/test_pluma_auto/pasos/assets/v5/assets/reparto/pastor.png`)**:
   Inspection via Python confirmed that `pastor.png` is an emergency canvas:
   - Size: 13,040 bytes.
   - Dimensions: 1280x720 RGBA.
   - Pixel at `(24, 24)`: `(212, 175, 55, 120)` gold border.
   If submitted to a vision model without validation, the model extracts the gold border and flat background as the character's visual identity.

4. **Gemini Client Failure Modes (`pasos/gemini_cliente.py:161-164, 307`)**:
   `gemini_cliente.ejecutar` raises a hard `RuntimeError` if `obtener_api_key()` returns empty string, or if all candidate models return HTTP 429, 503, or network errors:
   ```python
   raise RuntimeError(f"Fallo al invocar Gemini para {para}: {ultimo_error}")
   ```
   Calling code in `inversion_visual.py` must catch this exception and smoothly fall back.

5. **Test Runner Environment & Conventions**:
   Running `python3 -m pytest` failed with `No module named pytest`.
   However, `python3 -m unittest` is fully functional and native in Python 3.12. Furthermore, existing tests in the repo run via `python3 pasos/prueba_*.py` (e.g. `python3 pasos/prueba_presets.py` completed with `PRESETS OK: 84 comprobaciones pasan`).

---

## 2. Logic Chain

1. **From Observation 1 to Heuristic Translation**:
   Because `presets.json` already contains `paleta`, `trazo`, `relleno`, `luz`, `acabado`, and `evitar`, any failure of the Gemini Vision API can be intercepted to deterministically map these fields directly to the 8 required keys of `Style DNA` (`medium`, `palette_hex`, `palette_desc`, `linework`, `texture`, `lighting_style`, `negative_style`, `dna_block`).
   Converting `paleta` to `palette_desc` via Euclidean RGB nearest-neighbor matching against 20 standard named colors provides human-readable English color conditioning with zero runtime cost and zero dependencies.

2. **From Observation 2 and 3 to Image Validation**:
   Because active asset folders contain emergency canvases (`pastor.png`), and image generation failures can produce 0-byte or corrupted files, `extraer_adn_estilo` and `extraer_anclas_personaje` cannot assume input image validity.
   An image validator (`validar_imagen`) that verifies file existence, size (> 100 bytes), PIL header integrity (`verify()`), and absence of the `(212, 175, 55, 120)` border signature prevents poisoning of the vision extraction pipeline.

3. **From Observation 4 to Cascade Resilience**:
   Because `gemini_cliente.ejecutar` raises `RuntimeError` upon quota exhaustion (429) or missing keys, wrapping API invocations in a try/except block that falls back to preset heuristic translation guarantees that `extraer_adn_estilo` never crashes and always returns a contract-compliant dictionary.

4. **From Observation 5 to Verification Architecture**:
   Because `pytest` is not installed, the test suite must be executable via Python's native `unittest` runner (`python3 -m unittest`) and runnable as a standalone script (`python3 pasos/prueba_inversion_visual.py`). This ensures immediate execution without modifying the system environment.

---

## 3. Caveats

1. **Custom / Ad-hoc Presets**:
   If a user defines a new preset in the future without populating `datos.estilo.guia`, the heuristic fallback defaults to `DEFAULT_STYLE_DNA` (clean 2D digital vector animation baseline).
2. **Character Textual Descriptions in Catalog**:
   When a character sheet is an emergency canvas or missing, the fallback extracts textual anchors from `catalogo["reparto"][nombre]["descripcion"]` if accessible, or falls back to generic distinct attire descriptors if no catalog is passed into `extraer_anclas_personaje`.
3. **Pillow Dependency**:
   Image validation assumes `PIL` (Pillow) is available in Python, which was confirmed installed in the current environment.

---

## 4. Conclusion

1. **Heuristic Fallback Strategy**:
   Implement a 4-tier cascade in `pasos/inversion_visual.py`:
   `Cache -> Multimodal Gemini Vision -> Presets Guia Heuristic -> Universal Default DNA`.
   This guarantees that style extraction never returns `None` and always meets the 8-key interface contract.

2. **Image Validation & Emergency Rejection**:
   Integrate `validar_imagen` before any API call. Reject 0-byte, truncated, unreadable, and emergency canvases with gold border `(212, 175, 55, 120)` / size < 30 KB. If an emergency canvas is detected, route directly to heuristic fallback.

3. **Verification Suite**:
   Delivered complete test suite specification and executable code blueprint in `.agents/teamwork/teamwork_preview_explorer_m1_3/proposed_prueba_inversion_visual.py` covering:
   - Contract compliance (8 keys, regex hex patterns).
   - Preset fallbacks (Pluma_2, Pluma_3, Cartoon_Stick, androides).
   - Inferred preset IDs from paths.
   - Corrupted, 0-byte, and emergency canvas inputs.
   - HTTP 429 quota exhaustion and network chaos.

---

## 5. Verification Method

To independently verify the findings and test suite:

1. **Inspect Presets & Heuristic Translation**:
   ```bash
   python3 -c "
   import json
   with open('presets.json', 'r') as f:
       d = json.load(f)
   for p in d['presets']:
       print(p['id'], p['nombre'], list(p['datos']['estilo']['guia'].keys()))
   "
   ```

2. **Verify Emergency Canvas Detection on Existing Assets**:
   ```bash
   python3 -c "
   from PIL import Image
   import numpy as np
   img = Image.open('proyectos/test_pluma_auto/pasos/assets/v5/assets/reparto/pastor.png')
   arr = np.array(img.convert('RGB'))
   px = arr[24, 24]
   print('Pastor.png (24, 24) pixel:', px, '-> Gold border:', abs(px[0]-212)<=15 and abs(px[1]-175)<=15 and abs(px[2]-55)<=15)
   "
   ```

3. **Inspect Proposed Test Suite**:
   Read `.agents/teamwork/teamwork_preview_explorer_m1_3/proposed_prueba_inversion_visual.py`.
   Once `pasos/inversion_visual.py` is implemented by the authoring agent, the test suite can be run with:
   ```bash
   python3 -m unittest .agents/teamwork/teamwork_preview_explorer_m1_3/proposed_prueba_inversion_visual.py
   ```

4. **Invalidation Conditions**:
   - If `presets.json` structure is altered to remove `datos.estilo.guia`, the heuristic parser must be updated.
   - If emergency canvas border color signature changes from `(212, 175, 55, 120)`, the border detector must be adjusted.
