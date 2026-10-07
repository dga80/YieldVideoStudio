# Empirical Challenge Handoff Report: `pasos/inversion_visual.py`

**Agent**: `teamwork_preview_challenger_m1_1`  
**Archetype**: EMPIRICAL CHALLENGER (critic, specialist)  
**Target Module**: `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`  
**Verdict**: **`REQUEST_CHANGES`**  

---

## 1. Observation

Direct empirical observations, commands, outputs, and line references:

### Obs 1: Unhandled `AttributeError` in `sintetizar_adn_desde_preset` on null JSON fields
- **File**: `pasos/inversion_visual.py:336`, `340`, `361`, `365`, `369`
- **Code snippet**:
  ```python
  336: acabado = guia.get("acabado", "").strip()
  ...
  340: guia_txt = guia.get("guia", "").strip()
  ...
  361: trazo = guia.get("trazo", "").strip()
  ...
  365: relleno = guia.get("relleno", "").strip()
  ...
  369: luz = guia.get("luz", "").strip()
  ```
- **Execution**:
  ```bash
  python3 -c "
  import pasos.inversion_visual as iv
  from unittest.mock import patch
  with patch('pasos.inversion_visual.leer_json') as m:
      m.return_value = {'presets': [{'id': 'pr_null', 'datos': {'estilo': {'guia': {'acabado': None}}}}]}
      iv.sintetizar_adn_desde_preset('pr_null')
  "
  ```
- **Verbatim Error**:
  ```text
  AttributeError: 'NoneType' object has no attribute 'strip'
  ```
- **Cause**: In Python, `dict.get(key, default)` returns `None` if the key exists with value `None`. Subsequent `.strip()` calls crash unhandled.

### Obs 2: Cache Poisoning & Invariant Violation in `extraer_anclas_personaje`
- **File**: `pasos/inversion_visual.py:640-644`
- **Code snippet**:
  ```python
  640: huella = huella_fichero(ruta_personaje)
  641: if huella:
  642:     cache_h = os.path.join(BANCO, "dna", f"personaje_{huella}.json")
  643:     if os.path.isfile(cache_h):
  644:         data = leer_json(cache_h)
  645:         if isinstance(data, dict) and "name" in data and "anchors_block" in data:
  646:             return data
  ```
- **Execution**:
  ```bash
  python3 -c "
  import os, tempfile, json, pasos.inversion_visual as iv
  td = tempfile.mkdtemp(); iv.BANCO = td
  os.makedirs(os.path.join(td, 'dna'), exist_ok=True)
  from PIL import Image; p = os.path.join(td, 'char.png')
  Image.new('RGB', (100, 100), (255, 255, 255)).save(p)
  huella = iv.huella_fichero(p)
  with open(os.path.join(td, 'dna', f'personaje_{huella}.json'), 'w') as f:
      json.dump({'name': 'Marcus', 'anchors_block': ''}, f)
  res = iv.extraer_anclas_personaje(p, 'Marcus')
  print(res)
  "
  ```
- **Verbatim Output**:
  ```text
  {'name': 'Marcus', 'anchors_block': ''}
  ```
- **Cause**: Unlike `extraer_adn_estilo` which runs `_es_adn_valido` on cached data, `extraer_anclas_personaje` does NOT validate that `anchors_block` is non-empty or of type `str`. If corrupted or empty cache exists, it returns `anchors_block: ""` or `anchors_block: None`, directly violating the requirement that all returned schema fields must be non-empty strings.

### Obs 3: Unhandled `AttributeError` in `describir_paleta_hex` on non-string elements
- **File**: `pasos/inversion_visual.py:266-267`
- **Code snippet**:
  ```python
  266: for h in hex_list:
  267:     h_clean = h.strip().lstrip("#")
  ```
- **Execution**:
  ```bash
  python3 -c "import pasos.inversion_visual as iv; iv.describir_paleta_hex([None, 123, '#FF0000'])"
  ```
- **Verbatim Error**:
  ```text
  AttributeError: 'NoneType' object has no attribute 'strip'
  ```

### Obs 4: Unhandled `AttributeError` in `extraer_anclas_personaje` on non-string fallback
- **File**: `pasos/inversion_visual.py:623`
- **Code snippet**:
  ```python
  623: desc = descripcion_fallback.strip() if descripcion_fallback else ""
  ```
- **Execution**:
  ```bash
  python3 -c "import pasos.inversion_visual as iv; iv.extraer_anclas_personaje('/nonexistent.png', 'Marcus', descripcion_fallback=123)"
  ```
- **Verbatim Error**:
  ```text
  AttributeError: 'int' object has no attribute 'strip'
  ```

### Obs 5: Contract Inconsistency with E2E Suite `test_tier2_b04_zero_byte_image_file`
- **File**: `tests/test_e2e_visual_pipeline.py:1204` vs `pasos/inversion_visual.py:557`
- **Code snippet (`test_e2e_visual_pipeline.py`)**:
  ```python
  1204: def test_tier2_b04_zero_byte_image_file(self):
  1205:     with self.assertRaises((ValueError, Exception)):
  1206:         bridge_extraer_adn_estilo(self.zero_byte_path)
  ```
- **Code snippet (`inversion_visual.py`)**:
  ```python
  555: valida, motivo = validar_imagen(ruta_lamina)
  556: if not valida:
  557:     logger.info(f"Lámina '{ruta_lamina}' no válida para visión ({motivo}). Usando fallback heurístico.")
  558:     if pid:
  559:         return sintetizar_adn_desde_preset(pid)
  560:     return copy.deepcopy(DEFAULT_STYLE_DNA)
  ```
- **Execution**: `python3 -m unittest discover -s tests -p "test_*.py" -v`
- **Verbatim Error**:
  ```text
  FAIL: test_tier2_b04_zero_byte_image_file (test_e2e_visual_pipeline.TestTier2BoundaryCases.test_tier2_b04_zero_byte_image_file)
  AssertionError: (<class 'ValueError'>, <class 'Exception'>) not raised
  ```
- **Cause**: The test suite asserts that passing a 0-byte file must raise an exception. `inversion_visual.py` returns `DEFAULT_STYLE_DNA` instead of raising an error.

### Obs 6: Live API Coupling Breaks 5 Tests in Baseline E2E Suite
- **Execution**: `python3 -m unittest discover -s tests -p "test_*.py" -v`
- **Results**: `FAILED (failures=6, skipped=2)`
- **Verbatim Failures**:
  - `test_f1_03_dna_block_english_content`: Live Gemini output contained English token `"color"` (e.g. `"uniform color fills"`), triggering Spanish regex check `\b(estilo de|animacion|dibujo|color|reglas)\b`.
  - `test_f2_03_anchors_block_physical_traits`: Live Gemini described geometry (`"circular head"`, `"rectangular body"`) rather than expected mock traits (`coat`, `hair`, `scarf`).
  - `test_f5_03_replaced_with_textual_dna`: Live Gemini returned `"Flat vector"` instead of literal mock string `"2D vector"`.
  - `test_f6_02_character_anchors_slot_populated`: Marcus anchors from live Gemini lacked literal mock string `"navy blue work coat"`.
  - `test_scenario_s1_single_character_dialogue_interior`: Elena anchors from live Gemini described hair as `"brown"` instead of literal mock string `"auburn"`.

---

## 2. Logic Chain

1. From **Obs 1**: `sintetizar_adn_desde_preset` assumes `guia.get("acabado", "")` returns a string. When JSON explicitly sets `"acabado": null`, Python returns `None`, resulting in an unhandled `AttributeError` on `.strip()`. Therefore, `sintetizar_adn_desde_preset` crashes when encountering presets with null values.
2. From **Obs 2**: `extraer_anclas_personaje` only checks `"name" in data and "anchors_block" in data`. If a corrupted, poisoned, or empty cache file exists, it returns `anchors_block: ""` without validation or fallback repair. Therefore, the function fails the schema invariant that requires all string fields to be non-empty.
3. From **Obs 3 & Obs 4**: Utility and fallback routines (`describir_paleta_hex` and `_ancla_fallback`) invoke `.strip()` directly on input values without checking `isinstance(val, str)`. Therefore, any non-string parameter triggers an unhandled crash.
4. From **Obs 5**: The project's E2E test suite `test_e2e_visual_pipeline.py:1204` requires `extraer_adn_estilo` to raise an exception on 0-byte image files. Because `extraer_adn_estilo` returns default fallback instead, the official test suite fails.
5. From **Obs 6**: When `secretos/.env` is present in the environment, `pasos/inversion_visual.py` automatically initiates live network requests to Gemini Vision during unit tests, causing non-deterministic outputs and brittle test failures against hardcoded string assertions.

Combining (1), (2), (3), (4), and (5), the module contains critical unhandled exception vectors, cache integrity leaks, and test suite contract breakages.

---

## 3. Caveats

- In production with real, clean PNG images and active Gemini credentials, the primary path executes successfully.
- The 5 E2E string assertion failures (`"auburn"`, `"navy blue work coat"`, etc.) in `tests/test_e2e_visual_pipeline.py` stem from brittle test assertions designed around mock outputs rather than the live multimodal model's output variance. However, `test_tier2_b04` is a direct contract clash regarding error handling for 0-byte files.

---

## 4. Conclusion & Actionable Mitigations

**VERDICT**: **`REQUEST_CHANGES`**

The implementation in `pasos/inversion_visual.py` must be hardened before milestone approval:

### Required Fixes:
1. **Fix `sintetizar_adn_desde_preset` (lines 336-372)**:
   Safely sanitize values before calling `.strip()`:
   ```python
   acabado = str(guia.get("acabado") or "").strip()
   guia_txt = str(guia.get("guia") or "").strip()
   trazo = str(guia.get("trazo") or "").strip()
   relleno = str(guia.get("relleno") or "").strip()
   luz = str(guia.get("luz") or "").strip()
   ```
2. **Harden character cache validation (lines 642-646)**:
   Add a validator `_son_anclas_validas(data)` ensuring `data.get("anchors_block")` is a non-empty `str`:
   ```python
   def _son_anclas_validas(data: Optional[dict]) -> bool:
       return (
           isinstance(data, dict)
           and isinstance(data.get("name"), str) and bool(data["name"].strip())
           and isinstance(data.get("anchors_block"), str) and bool(data["anchors_block"].strip())
       )
   ```
   If cached data fails `_son_anclas_validas`, discard cache and fall back.
3. **Harden `describir_paleta_hex` (line 266)**:
   Add `if not isinstance(h, str): continue`.
4. **Harden `_ancla_fallback` (line 623)**:
   Safely handle non-string fallback:
   ```python
   desc = str(descripcion_fallback).strip() if descripcion_fallback and isinstance(descripcion_fallback, str) else ""
   ```
5. **Resolve 0-byte file contract**:
   Either raise `ValueError("Lámina vacía (0 bytes)")` when `ruta_lamina` is 0 bytes and no `preset_id` is specified (aligning with `test_tier2_b04`), or align `test_tier2_b04` if fallback is desired.
6. **Test Environment Live API Hooking**:
   Allow an environment variable or parameter to disable live API calls during unit tests (e.g. `TESTING=1` or mock fallback) to ensure deterministic offline execution of `tests/test_e2e_visual_pipeline.py`.

---

## 5. Verification Method

To verify these findings and reproduce all failures independently:

1. **Run the Stress Test Suite**:
   ```bash
   python3 -m unittest tests/test_stress_inversion_visual.py -v
   ```
   - Confirms Failures: `test_stress_24` (null preset fields crash), `test_stress_27` (empty character cache poisoning), `test_stress_30` (non-string palette crash).

2. **Run the Baseline Project E2E Suite**:
   ```bash
   python3 -m unittest discover -s tests -p "test_*.py" -v
   ```
   - Confirms 6 failing tests in `tests/test_e2e_visual_pipeline.py`.

3. **Invalidation Condition**:
   The verdict changes to `APPROVE` when:
   - All 31 tests in `tests/test_stress_inversion_visual.py` pass with 0 failures.
   - The contract for 0-byte files in `test_tier2_b04` is resolved.
