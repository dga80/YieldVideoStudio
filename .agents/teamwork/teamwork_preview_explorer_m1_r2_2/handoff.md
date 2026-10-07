# Handoff Report: 0-Byte Corrupt File Contract & Character Cache Validation

**Agent**: `teamwork_preview_explorer_m1_r2_2`  
**Roles**: Explorer, Investigator, Specialist  
**Working Directory**: `/Users/danidev/Desktop/asVideoStudio/.agents/teamwork/teamwork_preview_explorer_m1_r2_2`  
**Target Module**: `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`  
**Milestone**: M1 (Visual Style & Character DNA Inversion) — Iteration 2  
**Date**: 2026-10-06T20:20:30Z  

---

## 1. Observation

### Obs 1: `test_tier2_b04_zero_byte_image_file` Failure in E2E Suite
- **File**: `tests/test_e2e_visual_pipeline.py:1203-1205`
  ```python
  1203: def test_tier2_b04_zero_byte_image_file(self):
  1204:     with self.assertRaises((ValueError, Exception)):
  1205:         bridge_extraer_adn_estilo(self.zero_byte_path)
  ```
- **Command**: `python3 -m unittest tests/test_e2e_visual_pipeline.py -k test_tier2_b04_zero_byte_image_file`
- **Verbatim Error**:
  ```text
  FAIL: test_tier2_b04_zero_byte_image_file (test_e2e_visual_pipeline.TestTier2BoundaryCases.test_tier2_b04_zero_byte_image_file)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "/Users/danidev/Desktop/asVideoStudio/tests/test_e2e_visual_pipeline.py", line 1204, in test_tier2_b04_zero_byte_image_file
      with self.assertRaises((ValueError, Exception)):
  AssertionError: (<class 'ValueError'>, <class 'Exception'>) not raised
  ```
- **Code Inspection in `pasos/inversion_visual.py:554-561`**:
  ```python
  554:     # 2. Validación física y anti-lienzo de emergencia de la lámina
  555:     valida, motivo = validar_imagen(ruta_lamina)
  556:     if not valida:
  557:         logger.info(f"Lámina '{ruta_lamina}' no válida para visión ({motivo}). Usando fallback heurístico.")
  558:         if pid:
  559:             return sintetizar_adn_desde_preset(pid)
  560:         return copy.deepcopy(DEFAULT_STYLE_DNA)
  ```
  When `ruta_lamina` is a 0-byte file (e.g., `self.zero_byte_path`) and no `preset_id` is passed, `inferir_preset_id` returns `None`. `validar_imagen` fails with `motivo = "fichero_vacio_0_bytes"`. Because `pid` is `None`, line 560 silently returns `copy.deepcopy(DEFAULT_STYLE_DNA)` instead of raising an exception.

### Obs 2: Character Anchor Cache Poisoning in `extraer_anclas_personaje`
- **File**: `tests/test_stress_inversion_visual.py:450-463`
  ```python
  450: def test_stress_27_character_cache_with_empty_anchors_block(self):
  451:     """Character cache with empty anchors_block: does extraer_anclas_personaje reject it or return empty?"""
  ...
  456:     with open(cache_path, "w") as f:
  457:         json.dump({"name": "TestChar", "anchors_block": ""}, f)
  458:     char = iv.extraer_anclas_personaje(img, "TestChar")
  459:     try:
  460:         assert_character_schema_invariant(self, char, "character cache with empty anchors")
  461:     except AssertionError as ae:
  462:         self.fail(f"VULNERABILITY CONFIRMED: Character cache returned empty anchors_block: {ae}")
  ```
- **Command**: `python3 -m unittest tests/test_stress_inversion_visual.py -k test_stress_27`
- **Verbatim Error**:
  ```text
  FAIL: test_stress_27_character_cache_with_empty_anchors_block (test_stress_inversion_visual.TestStressInversionVisual.test_stress_27_character_cache_with_empty_anchors_block)
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "/Users/danidev/Desktop/asVideoStudio/tests/test_stress_inversion_visual.py", line 462, in test_stress_27_character_cache_with_empty_anchors_block
      self.fail(f"VULNERABILITY CONFIRMED: Character cache returned empty anchors_block: {ae}")
  AssertionError: VULNERABILITY CONFIRMED: Character cache returned empty anchors_block: False is not true : 'anchors_block' must not be empty. Context: character cache with empty anchors
  ```
- **Code Inspection in `pasos/inversion_visual.py:636-644`**:
  ```python
  636:     # 2. Comprobar caché de contenido por huella SHA-256
  637:     huella = huella_fichero(ruta_personaje)
  638:     if huella:
  639:         cache_h = os.path.join(BANCO, "dna", f"personaje_{huella}.json")
  640:         if os.path.isfile(cache_h):
  641:             data = leer_json(cache_h)
  642:             if isinstance(data, dict) and "name" in data and "anchors_block" in data:
  643:                 return data
  ```
  Line 642 checks only key presence (`"name" in data and "anchors_block" in data`). It does NOT check whether `anchors_block` is a string, whether it is non-empty, or whether `name` is non-empty. Contrast this with `_es_adn_valido(data)` in line 568 for Style DNA, which strictly validates all fields.

### Obs 3: Cache Writer Invariance Leak in `_guardar_cache_huella`
- **Code Inspection in `pasos/inversion_visual.py:439-447`**:
  ```python
  439: def _guardar_cache_huella(prefijo: str, ruta_fichero: str, datos: dict) -> None:
  440:     if not ruta_fichero or not os.path.isfile(ruta_fichero):
  441:         return
  442:     try:
  443:         huella = huella_fichero(ruta_fichero)
  444:         if huella:
  445:             ruta_global = os.path.join(BANCO, "dna", f"{prefijo}_{huella}.json")
  446:             escribir_json(ruta_global, datos)
  ```
  `_guardar_cache_huella` writes whatever dictionary is passed without validating that the payload adheres to either `_es_adn_valido` (for `prefijo == "estilo"`) or character anchor validity (for `prefijo == "personaje"`).

---

## 2. Logic Chain

1. **Rejection of 0-Byte / Corrupt Style Sheets**:
   - From Obs 1, when a caller invokes `extraer_adn_estilo(ruta_lamina)` with a 0-byte or corrupted file and no preset ID is provided, the pipeline must reject the input with `ValueError` as specified by `test_tier2_b04_zero_byte_image_file`.
   - Returning `DEFAULT_STYLE_DNA` silently masks asset corruption (e.g. truncated downloads, incomplete writes) and breaks contract expectations.
   - However, when a valid preset ID *is* supplied (e.g. `extraer_adn_estilo(corrupt_file, preset_id="pr1a0eef81dc7")`), the pipeline should gracefully fall back to the preset's heuristic DNA from `presets.json` (as verified by `test_fichero_cero_bytes` and `test_fichero_corrupto` in `pasos/prueba_inversion_visual.py`).
   - If the supplied `preset_id` is invalid, empty, or not found in `presets.json`, it must raise `ValueError(f"Archivo de imagen inválido o corrupto: {ruta_lamina}")`.
   - When `ruta_lamina` is `None` (pure preset invocation, step 1), it must continue returning preset DNA or default DNA without raising an error.

2. **Integrity Guarding for Character Anchor Cache**:
   - From Obs 2, `extraer_anclas_personaje` only checks key presence in cached JSON files. If a cache file is corrupted or contains `{"name": "...", "anchors_block": ""}`, it directly returns the empty string, violating `PROJECT.md § Interface Contracts` and triggering `test_stress_27`.
   - Introducing `_son_anclas_validas(anclas: Optional[dict]) -> bool` mirrors `_es_adn_valido` for Style DNA and asserts that both `"name"` and `"anchors_block"` are non-empty strings (`isinstance(..., str) and bool(...strip())`).
   - If cached character data fails `_son_anclas_validas`, `extraer_anclas_personaje` must discard the cache entry and fall back to Gemini Vision or `_ancla_fallback()`.

3. **Defensive Cache Writing**:
   - From Obs 3, ensuring that `_guardar_cache_huella` checks `_son_anclas_validas` when saving character anchors prevents write-side cache poisoning.

---

## 3. Caveats

1. **Test Suite Alignment in `tests/test_stress_inversion_visual.py`**:
   - `test_stress_01_zero_byte_file` through `test_stress_10` in `tests/test_stress_inversion_visual.py` were originally written by Challenger 1 expecting `extraer_adn_estilo` to always return fallback DNA on corrupted files without raising exceptions.
   - However, Challenger 1's own handoff report (Obs 5) and the Milestone 1 Gate Status noted that this directly conflicted with the authoritative `test_tier2_b04_zero_byte_image_file` in `tests/test_e2e_visual_pipeline.py`.
   - Raising `ValueError` on 0-byte/corrupt files without preset correctly satisfies `test_tier2_b04`. The Worker or Test Writer should update `test_stress_01` (and boundary tests 02-10) in `test_stress_inversion_visual.py` to expect `ValueError` when no preset is provided, or supply a valid preset ID to test fallback.
2. **Offline Determinism / Test Isolation**:
   - While `test_tier2_b04` and `test_stress_27` are fixed by these changes, live Gemini Vision calls in `test_stress_inversion_visual.py` and `test_e2e_visual_pipeline.py` are separately addressed by Explorer 3.

---

## 4. Conclusion & Recommendations for Worker

The Worker should apply the following precise changes to `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`:

### Recommendation 1: Add Helper `_buscar_preset`
In `pasos/inversion_visual.py`, immediately before `sintetizar_adn_desde_preset` (around line 314):

```python
def _buscar_preset(preset_id: Optional[str]) -> Optional[dict]:
    """Busca un preset por ID en presets.json."""
    if not preset_id or not isinstance(preset_id, str):
        return None
    pid_limpio = preset_id.strip()
    if not pid_limpio:
        return None
    p_path = os.path.join(RAIZ_ESTUDIO, "presets.json")
    if os.path.exists(p_path):
        try:
            datos = leer_json(p_path, por_defecto={})
            for pr in datos.get("presets", []):
                if pr.get("id") == pid_limpio:
                    return pr
        except Exception as e:
            logger.warning(f"Error leyendo presets.json: {e}")
    return None
```
And refactor `sintetizar_adn_desde_preset`:
```python
def sintetizar_adn_desde_preset(preset_id: str) -> dict:
    """Traduce deterministamente datos.estilo.guia de presets.json a las 8 claves del contrato."""
    preset_encontrado = _buscar_preset(preset_id)
    if not preset_encontrado:
        return copy.deepcopy(DEFAULT_STYLE_DNA)

    guia = preset_encontrado.get("datos", {}).get("estilo", {}).get("guia", {})
    if not guia:
        return copy.deepcopy(DEFAULT_STYLE_DNA)
    ...
```

---

### Recommendation 2: Add Validator `_son_anclas_validas`
In `pasos/inversion_visual.py`, right after `_es_adn_valido` (around line 424):

```python
def _son_anclas_validas(anclas: Optional[dict]) -> bool:
    """Verifica que un diccionario cumpla estrictamente con el contrato de Character Anchors."""
    if not isinstance(anclas, dict):
        return False
    if "name" not in anclas or "anchors_block" not in anclas:
        return False
    if not isinstance(anclas["name"], str) or not anclas["name"].strip():
        return False
    if not isinstance(anclas["anchors_block"], str) or not anclas["anchors_block"].strip():
        return False
    return True
```

---

### Recommendation 3: Enforce 0-Byte / Corrupt File Rejection in `extraer_adn_estilo`
In `pasos/inversion_visual.py:554-561`, replace:

```python
    # 2. Validación física y anti-lienzo de emergencia de la lámina
    valida, motivo = validar_imagen(ruta_lamina)
    if not valida:
        logger.info(f"Lámina '{ruta_lamina}' no válida para visión ({motivo}). Usando fallback heurístico.")
        if pid:
            return sintetizar_adn_desde_preset(pid)
        return copy.deepcopy(DEFAULT_STYLE_DNA)
```

With:

```python
    # 2. Validación física y anti-lienzo de emergencia de la lámina
    valida, motivo = validar_imagen(ruta_lamina)
    if not valida:
        logger.info(f"Lámina '{ruta_lamina}' no válida para visión ({motivo}).")
        if pid:
            pr = _buscar_preset(pid)
            if pr and pr.get("datos", {}).get("estilo", {}).get("guia"):
                return sintetizar_adn_desde_preset(pid)
        raise ValueError(f"Archivo de imagen inválido o corrupto: {ruta_lamina}")
```

---

### Recommendation 4: Enforce Cache Validation in `extraer_anclas_personaje`
In `pasos/inversion_visual.py:640-644`, replace:

```python
        cache_h = os.path.join(BANCO, "dna", f"personaje_{huella}.json")
        if os.path.isfile(cache_h):
            data = leer_json(cache_h)
            if isinstance(data, dict) and "name" in data and "anchors_block" in data:
                return data
```

With:

```python
        cache_h = os.path.join(BANCO, "dna", f"personaje_{huella}.json")
        if os.path.isfile(cache_h):
            data = leer_json(cache_h)
            if _son_anclas_validas(data):
                return data
            logger.warning(f"Caché de anclas corrupta o vacía en {cache_h}, ignorando.")
```

And in line 660, replace:
```python
        anclas = _procesar_respuesta_gemini_personaje(texto_resp, nombre)
        if anclas and "name" in anclas and "anchors_block" in anclas and anclas["anchors_block"]:
            _guardar_cache_huella("personaje", ruta_personaje, anclas)
            return anclas
```
With:
```python
        anclas = _procesar_respuesta_gemini_personaje(texto_resp, nombre)
        if _son_anclas_validas(anclas):
            _guardar_cache_huella("personaje", ruta_personaje, anclas)
            return anclas
```

And in line 620:
```python
    nombre = str(nombre_personaje).strip() if (nombre_personaje and str(nombre_personaje).strip()) else "character"
```

---

### Recommendation 5: Guard Cache Writing in `_guardar_cache_huella`
In `pasos/inversion_visual.py:440-442`, add write-side validation:

```python
    if prefijo == "estilo" and not _es_adn_valido(datos):
        return
    if prefijo == "personaje" and not _son_anclas_validas(datos):
        return
```

---

## 5. Verification Method

To independently verify the implementation:

1. **Verify 0-byte Image Rejection (`test_tier2_b04`)**:
   ```bash
   python3 -c "
   import tempfile, os
   from pasos.inversion_visual import extraer_adn_estilo
   with tempfile.NamedTemporaryFile(suffix='.png') as f:
       try:
           extraer_adn_estilo(f.name)
           print('FAIL: ValueError not raised')
       except ValueError as e:
           print(f'PASS: Correctly raised ValueError: {e}')
   "
   ```
   *Expected outcome*: `PASS: Correctly raised ValueError: Archivo de imagen inválido o corrupto: ...`

2. **Verify Heuristic Fallback with Valid Preset Remains Operational**:
   ```bash
   python3 -c "
   import tempfile, os
   from pasos.inversion_visual import extraer_adn_estilo
   with tempfile.NamedTemporaryFile(suffix='.png') as f:
       dna = extraer_adn_estilo(f.name, preset_id='pr1a0eef81dc7')
       assert 'medium' in dna and len(dna['medium']) > 0
       print('PASS: Fallback to preset succeeded')
   "
   ```
   *Expected outcome*: `PASS: Fallback to preset succeeded`

3. **Verify Character Cache Poisoning Defense (`test_stress_27`)**:
   ```bash
   python3 -m unittest tests/test_stress_inversion_visual.py -k test_stress_27 -v
   ```
   *Expected outcome*: `test_stress_27_character_cache_with_empty_anchors_block ... ok`

4. **Run Milestone 1 Unit Suite**:
   ```bash
   python3 pasos/prueba_inversion_visual.py -v
   ```
   *Expected outcome*: `Ran 17 tests in ~0.09s ... OK`

5. **Run E2E Boundary Test**:
   ```bash
   python3 -m unittest tests/test_e2e_visual_pipeline.py -k test_tier2_b04_zero_byte_image_file -v
   ```
   *Expected outcome*: `test_tier2_b04_zero_byte_image_file ... ok`
