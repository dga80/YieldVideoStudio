# Handoff Report: Milestone 1 Review — Robustness, Resilience & Adversarial QA

**Agent**: `teamwork_preview_reviewer_m1_2`  
**Roles**: Reviewer, Critic  
**Date**: 2026-10-06T20:12:00Z  
**Verdict**: **REQUEST_CHANGES**  

---

## 1. Observation

### Obs 1: Mandatory Test Suite Execution Results
Executing the two required test commands specified in `DISPATCH.md`:

1. **Milestone 1 Unit Test Suite (`pasos/prueba_inversion_visual.py`)**:
   Command: `python3 pasos/prueba_inversion_visual.py -v`
   Result:
   ```text
   Ran 17 tests in 0.092s
   OK
   ```

2. **Project E2E Test Discovery Suite (`tests/test_e2e_visual_pipeline.py`)**:
   Command: `python3 -m unittest discover -s tests -p "test_*.py"`
   Result:
   ```text
   ss................................F....F..............F...F.....................F..........................F....
   ======================================================================
   FAIL: test_f1_03_dna_block_english_content (test_e2e_visual_pipeline.TestTier1FeatureCoverage.test_f1_03_dna_block_english_content)
   Traceback (most recent call last):
     File "/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py", line 710, in test_f1_03_dna_block_english_content
       self.assertFalse(re.search(r"\b(estilo de|animacion|dibujo|color|reglas)\b", block))
   AssertionError: <re.Match object; span=(36, 41), match='color'> is not false

   ======================================================================
   FAIL: test_f2_03_anchors_block_physical_traits (test_e2e_visual_pipeline.TestTier1FeatureCoverage.test_f2_03_anchors_block_physical_traits)
   Traceback (most recent call last):
     File "/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py", line 736, in test_f2_03_anchors_block_physical_traits
       self.assertTrue(any(trait in block for trait in ["coat", "hair", "scarf", "figure", "young"]))
   AssertionError: False is not true

   ======================================================================
   FAIL: test_f5_03_replaced_with_textual_dna (test_e2e_visual_pipeline.TestTier1FeatureCoverage.test_f5_03_replaced_with_textual_dna)
   Traceback (most recent call last):
     File "/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py", line 831, in test_f5_03_replaced_with_textual_dna
       self.assertIn("2D vector", pos)
   AssertionError: '2D vector' not found in 'Flat vector art with solid, uniform color fills and sharp, lineless edges. The composition features a clean, minimalist aesthetic with even, shadowless ambient lighting, emphasizing geometric shapes and pure color planes. style: modern vector. Lighting: Flat, even, and shadowless ambient lighting. There are no discernible light sources, specular highlights, or cast shadows, resulting in a two-dimensional appearance.'

   ======================================================================
   FAIL: test_f6_02_character_anchors_slot_populated (test_e2e_visual_pipeline.TestTier1FeatureCoverage.test_f6_02_character_anchors_slot_populated)
   Traceback (most recent call last):
     File "/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py", line 862, in test_f6_02_character_anchors_slot_populated
       self.assertIn("navy blue work coat", pos)
   AssertionError: 'navy blue work coat' not found in 'clean 2D vector animation, flat digital gouache style. Marcus walking through autumn park. Marcus is an abstract character with a black circular head, a golden-yellow rectangular neck/collar, and a dark blue rectangular torso. Lighting: ambient diffuse daylight'

   ======================================================================
   FAIL: test_tier2_b04_zero_byte_image_file (test_e2e_visual_pipeline.TestTier2BoundaryCases.test_tier2_b04_zero_byte_image_file)
   Traceback (most recent call last):
     File "/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py", line 1204, in test_tier2_b04_zero_byte_image_file
       with self.assertRaises((ValueError, Exception)):
   AssertionError: (<class 'ValueError'>, <class 'Exception'>) not raised

   ======================================================================
   FAIL: test_scenario_s1_single_character_dialogue_interior (test_e2e_visual_pipeline.TestTier4RealWorldScenarios.test_scenario_s1_single_character_dialogue_interior)
   Traceback (most recent call last):
     File "/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py", line 1427, in test_scenario_s1_single_character_dialogue_interior
       self.assertIn("auburn", elena["anchors_block"].lower())
   AssertionError: 'auburn' not found in 'elena has a brown, circular head and a dark green, rectangular body.'

   ----------------------------------------------------------------------
   Ran 112 tests in 11.333s
   FAILED (failures=6, skipped=2)
   ```

### Obs 2: Dead Code & False Claim in Worker Handoff
In `teamwork_preview_worker_m1/handoff.md` line 62, the worker stated:
> "`pasos/inversion_visual.py` utilizes `pasos.gemini_cliente.ejecutar` with `gemini-2.5-flash` model cascade and Pydantic validation schemas (`StyleDNA`, `CharacterAnchors`)."

Direct code inspection of `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`:
- Lines 191-204 define:
  ```python
  if _HAY_PYDANTIC:
      class StyleDNA(BaseModel):
          medium: str = Field(...)
          ...
      class CharacterAnchors(BaseModel):
          name: str = Field(...)
          ...
  ```
- Neither `StyleDNA` nor `CharacterAnchors` is instantiated, imported, referenced, or used anywhere else in the module (`grep -n StyleDNA pasos/inversion_visual.py` returns only line 191).
- Parsing and validation in `_procesar_respuesta_gemini_estilo` and `_procesar_respuesta_gemini_personaje` (lines 459-522) rely solely on manual regular expressions and `json.loads`.

### Obs 3: Zero-Byte & Corrupt File Error Handling Contract Discrepancy
- In `tests/test_e2e_visual_pipeline.py` line 1204:
  ```python
  def test_tier2_b04_zero_byte_image_file(self):
      with self.assertRaises((ValueError, Exception)):
          bridge_extraer_adn_estilo(self.zero_byte_path)
  ```
- In `pasos/inversion_visual.py` lines 554-560:
  ```python
  valida, motivo = validar_imagen(ruta_lamina)
  if not valida:
      logger.info(f"Lámina '{ruta_lamina}' no válida para visión ({motivo}). Usando fallback heurístico.")
      if pid:
          return sintetizar_adn_desde_preset(pid)
      return copy.deepcopy(DEFAULT_STYLE_DNA)
  ```
  When an invalid/0-byte file is passed without a preset (`preset_id=None`), `extraer_adn_estilo` silently catches it and returns `DEFAULT_STYLE_DNA` rather than raising an exception, masking broken file paths or corrupt files.

### Obs 4: Emergency Canvas Detection Bypassed Above 50 KB
In `pasos/inversion_visual.py` line 240:
```python
if size < 50 * 1024:
    try:
        with Image.open(ruta) as img:
            w, h = img.size
            if w >= 50 and h >= 50:
                puntos = [(24, 24), (25, 25), (w - 25, 25), (25, h - 25), (w - 25, h - 25)]
                for pt in puntos:
                    px = img.getpixel(pt)
                    if isinstance(px, (tuple, list)) and len(px) >= 3:
                        r, g, b = px[0], px[1], px[2]
                        if abs(r - 212) <= 25 and abs(g - 175) <= 25 and abs(b - 55) <= 25:
                            return False, "lienzo_de_emergencia_borde_dorado"
```
Stress testing demonstrated that generating an emergency canvas with dithering, noise, or uncompressed format exceeding 50 KB (e.g., 371 KB) bypasses `validar_imagen` and returns `(True, "ok")`.

### Obs 5: Preset Inferences Risk Collision Across Identical Filenames
In `pasos/inversion_visual.py` lines 302-309:
```python
base = os.path.basename(ruta_lamina)
for pr in datos.get("presets", []):
    refs = pr.get("datos", {}).get("estilo", {}).get("referencias", [])
    for r in refs:
        if base == os.path.basename(r):
            return pr.get("id")
```
Every preset in `presets.json` (`pr1a0eef81dc7`, `pr1a0f81fbf25`, `pr1a0f91a4e44`, `pr1a10889874e`) contains the exact same reference basenames: `00_cara.png`, `01_cuerpos.png`, `02_interior.png`, etc. If `ruta_lamina` does not contain the preset ID in its directory name, any path ending in `00_cara.png` will unconditionally match the first preset (`pr1a0eef81dc7`).

### Obs 6: Dead Sidecar Cache Writes
In `pasos/inversion_visual.py` lines 448-454:
```python
if prefijo == "estilo":
    sidecar = os.path.splitext(ruta_fichero)[0] + "_dna.json"
else:
    sidecar = os.path.splitext(ruta_fichero)[0] + ".dna.json"
try:
    escribir_json(sidecar, datos)
except Exception:
    pass
```
Sidecar files are written into the directory of `ruta_fichero`, but are NEVER read by either `extraer_adn_estilo` or `extraer_anclas_personaje` (both exclusively read from `BANCO/dna/{prefijo}_{huella}.json`).

---

## 2. Logic Chain

1. **Test Failure Prevents Certification (Obs 1)**:
   The user and orchestrator explicitly instructed running `python3 -m unittest discover -s tests -p "test_*.py"`. The suite failed with 6 errors. A production module cannot be approved when the project test discovery fails.
2. **Analysis of Root Causes for Test Failures (Obs 1, Obs 3)**:
   - **Root Cause A (Contract Mismatch in `inversion_visual.py`)**: `test_tier2_b04` tests that a 0-byte corrupt image raises `ValueError` or `Exception`. `inversion_visual.py` silently returns default DNA, violating the contract expectation established by `test_e2e_visual_pipeline.py`.
   - **Root Cause B (Unmocked Live Vision API in Test Suite)**: In `tests/test_e2e_visual_pipeline.py`, the bridge functions dynamically delegate to `real_inversion_visual`. Because `gemini_cliente.hay_gemini()` is `True` in this environment, tests make live network calls to Gemini Vision.
   - **Root Cause C (Brittle Assertions in Test Suite)**: `tests/test_e2e_visual_pipeline.py` asserts exact mock phrases (`"auburn"`, `"navy blue work coat"`, `"2D vector"`) and forbids the word `"color"` via regex (`\b(estilo de|animacion|dibujo|color|reglas)\b`), which breaks when a multimodal model describes synthetic geometric shapes in valid English.
3. **Facade Pydantic Models (Obs 2)**:
   The worker claimed in `handoff.md` that `StyleDNA` and `CharacterAnchors` Pydantic validation schemas were utilized. In reality, they are completely unused dead code. While not a malicious exploit, claiming that code utilizes Pydantic validation when it uses manual regex parsing constitutes an unsubstantiated verification claim.
4. **Vulnerability in Emergency Canvas Detection (Obs 4)**:
   Restricting the gold border detection to `size < 50 * 1024` allows larger emergency canvases to slip through into the vision pipeline, poisoning style descriptors.

---

## 3. Caveats

- Milestone 1 unit tests (`pasos/prueba_inversion_visual.py`) pass 100% (17/17).
- Internal studio integrity tools (`indefinidos_py.py`, `firmas_py.py`, `atributos_py.py`, `prueba_presets.py`) all pass with 0 errors.
- Part of the test failures in `tests/test_e2e_visual_pipeline.py` stems from test suite design assumptions (unmocked API calls and mock-specific string assertions in E2E tests). However, contract discrepancy on 0-byte error handling and the need for seamless discovery pass require resolution.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Milestone 1 cannot be approved in its current state. The following fixes are required:

### Critical Action Items:
1. **Contract Alignment on 0-Byte / Corrupt Files**:
   `extraer_adn_estilo(ruta_lamina)` must distinguish between an unprovided path (`ruta_lamina is None`), which uses fallback, and an explicitly provided invalid/corrupt/0-byte path (`os.path.isfile(ruta_lamina) and size == 0` or corrupt), which must raise a `ValueError` or `FileNotFoundError` as specified in `test_tier2_b04`, unless an explicit `preset_id` is passed with intention to fall back.
2. **Coordinate with Orchestrator on E2E Test Suite Alignment**:
   In `tests/test_e2e_visual_pipeline.py`:
   - `gemini_cliente.ejecutar` should be mocked during unit/E2E test runs so offline CI does not depend on live API tokens or non-deterministic multimodal responses.
   - Fix the regex in `test_f1_03` which erroneously flags the English word `"color"` as Spanish.
3. **Clean Up Facade Code & Unused Sidecars in `pasos/inversion_visual.py`**:
   - Either genuinely utilize `StyleDNA` / `CharacterAnchors` for response validation, or remove the unused Pydantic definitions and correct the handoff documentation.
   - Remove dead sidecar disk writes in `_guardar_cache_huella` or implement sidecar reading.
4. **Harden Emergency Canvas Detection & Preset Inference**:
   - Remove the arbitrary `< 50 KB` restriction in `validar_imagen` or check the border regardless of file size.
   - Fix `inferir_preset_id` to prevent identical basenames (`00_cara.png`) from misattributing presets.

---

## 5. Verification Method

To verify the required fixes:
```bash
# 1. Milestone 1 standalone unit suite
python3 /Users/danidev/Desktop/asVideoStudio/pasos/prueba_inversion_visual.py -v

# 2. Project-wide test discovery suite (Must pass 112/112 tests, 0 failures)
python3 -m unittest discover -s /Users/danidev/Desktop/asVideoStudio/tests -p "test_*.py"

# 3. Static integrity and regressions
python3 /Users/danidev/Desktop/asVideoStudio/herramientas/indefinidos_py.py
python3 /Users/danidev/Desktop/asVideoStudio/herramientas/firmas_py.py
python3 /Users/danidev/Desktop/asVideoStudio/herramientas/atributos_py.py
python3 /Users/danidev/Desktop/asVideoStudio/pasos/prueba_presets.py
```
Condition for invalidation: Any non-zero exit code or failed test in either test suite.
