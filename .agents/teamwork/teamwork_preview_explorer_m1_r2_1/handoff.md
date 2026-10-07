# Handoff Report: Null Safety, Defensive Attribute Handling & Dead Code Analysis

**Agent**: `teamwork_preview_explorer_m1_r2_1`  
**Archetype**: Teamwork Explorer (Investigation & Synthesis)  
**Target Module**: `/Users/danidev/Desktop/asVideoStudio/pasos/inversion_visual.py`  
**Milestone**: Milestone 1 Iteration 2 (Visual Style & Character DNA Inversion)  
**Date**: 2026-10-06T20:21:00Z  

---

## 1. Observation

Direct empirical observations, reproduction commands, line numbers, and verbatim outputs:

### Obs 1: `AttributeError` on `None` values in `sintetizar_adn_desde_preset`
- **File**: `pasos/inversion_visual.py:336`, `340`, `361`, `365`, `369`
- **Code**:
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
- **Reproduction**:
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
- **Root Cause**: `dict.get(key, default)` returns `None` when the key explicitly maps to `None` in JSON. Calling `.strip()` directly crashes. Additionally, line 331 (`preset_encontrado.get("datos", {}).get("estilo", {}).get("guia", {})`) crashes with `AttributeError: 'NoneType' object has no attribute 'get'` if `"datos"` or `"estilo"` is `None`.

### Obs 2: `AttributeError` in `describir_paleta_hex` on non-string or `None` elements
- **File**: `pasos/inversion_visual.py:266-267`
- **Code**:
  ```python
  266: for h in hex_list:
  267:     h_clean = h.strip().lstrip("#")
  ```
- **Reproduction**:
  ```bash
  python3 -c "import pasos.inversion_visual as iv; iv.describir_paleta_hex([None, 123, '#FF0000', True])"
  ```
- **Verbatim Error**:
  ```text
  AttributeError: 'NoneType' object has no attribute 'strip'
  ```
- **Root Cause**: Iterates over `hex_list` assuming every element is a string. When elements are `None`, integers, or booleans, `.strip()` raises `AttributeError`. Furthermore, if `hex_list` is `None`, `TypeError: 'NoneType' object is not iterable` occurs.

### Obs 3: `AttributeError` in `_ancla_fallback` on non-string truthy `descripcion_fallback`
- **File**: `pasos/inversion_visual.py:623`
- **Code**:
  ```python
  623: desc = descripcion_fallback.strip() if descripcion_fallback else ""
  ```
- **Reproduction**:
  ```bash
  python3 -c "import pasos.inversion_visual as iv; iv.extraer_anclas_personaje('/nonexistent.png', 'Marcus', descripcion_fallback=12345)"
  ```
- **Verbatim Error**:
  ```text
  AttributeError: 'int' object has no attribute 'strip'
  ```
- **Root Cause**: Python evaluates non-zero integers, non-empty collections, and `True` as truthy. `12345.strip()` raises `AttributeError`.

### Obs 4: Unused Pydantic models & dead import blocks
- **File**: `pasos/inversion_visual.py:28-32` and `190-204`
- **Code**:
  ```python
  28: try:
  29:     from pydantic import BaseModel, Field
  30:     _HAY_PYDANTIC = True
  31: except ImportError:
  32:     _HAY_PYDANTIC = False
  ...
  190: if _HAY_PYDANTIC:
  191:     class StyleDNA(BaseModel):
  ...
  201:     class CharacterAnchors(BaseModel):
  ...
  ```
- **Search Verification**: Global `grep_search` across entire workspace (`asVideoStudio`) for `StyleDNA`, `CharacterAnchors`, and `_HAY_PYDANTIC` showed 0 consumers, 0 imports, and 0 instantiations.
- **Contract Reference**: `PROJECT.md § Interface Contracts` mandates plain `dict` returns:
  `extraer_adn_estilo(...) -> dict` and `extraer_anclas_personaje(...) -> dict`. Pure dictionary validation is already performed natively by `CLAVES_ADN_ESPERADAS` and `_es_adn_valido`.

### Obs 5: Character cache validation omission in `extraer_anclas_personaje`
- **File**: `pasos/inversion_visual.py:642-643` and `660`
- **Code**:
  ```python
  642: if isinstance(data, dict) and "name" in data and "anchors_block" in data:
  643:     return data
  ```
- **Stress Test Failure**: `test_stress_27_character_cache_with_empty_anchors_block` in `tests/test_stress_inversion_visual.py`:
  ```text
  AssertionError: VULNERABILITY CONFIRMED: Character cache returned empty anchors_block: False is not true : 'anchors_block' must not be empty.
  ```
- **Root Cause**: Unlike `extraer_adn_estilo` which validates cache with `_es_adn_valido(data)`, `extraer_anclas_personaje` accepts `anchors_block: ""` or `None` from cached files, violating the schema invariant.

---

## 2. Logic Chain

1. From **Obs 1**: `sintetizar_adn_desde_preset` accesses dictionary fields with `.get(key, "")`. When a JSON field explicitly contains `null`, `.get()` returns `None`. Calling `.strip()` on `None` causes an unhandled `AttributeError`, failing `test_stress_24`. Additionally, chained `.get()` at line 331 crashes if parent keys are `None`.
2. From **Obs 2**: `describir_paleta_hex` does not check `isinstance(h, str)` before `.strip()`. Non-string elements cause an unhandled `AttributeError`, failing `test_stress_30`.
3. From **Obs 3**: `_ancla_fallback` tests truthiness (`if descripcion_fallback`) instead of string type (`if isinstance(descripcion_fallback, str)`). When passed non-string arguments such as numeric IDs, it crashes with `AttributeError`.
4. From **Obs 4**: `StyleDNA` and `CharacterAnchors` models are defined conditionally under `_HAY_PYDANTIC` but never used anywhere in the codebase. Removing them eliminates dead code, avoids an unnecessary dependency try-import, and simplifies maintenance.
5. From **Obs 5**: Character cache lookup does not validate that `anchors_block` is a non-empty string. Creating a companion validator `_son_anclas_validas` ensures corrupted or empty cache files are discarded and regenerated.

---

## 3. Caveats

- **Scope boundary**: Test suite live API mocking (`TESTING=1` / deterministic test doubles) and the 0-byte file contract exception (`ValueError` vs fallback) are assigned to Explorer 2 (`teamwork_preview_explorer_m1_r2_2`) and Explorer 3 (`teamwork_preview_explorer_m1_r2_3`). This report provides the exact null-safety, defensive programming, and code hygiene specifications for the Worker.
- **Backwards compatibility**: All proposed recommendations preserve the exact dictionary keys, schemas, and default values defined in `PROJECT.md § Interface Contracts`.

---

## 4. Conclusion & Actionable Recommendations for Worker

The Worker should apply the following line-by-line changes to `pasos/inversion_visual.py`:

### Change 1: Remove Dead Pydantic Imports and Models
- **Target**: Lines 28-32 and lines 190-204
- **Action**: Delete both blocks.
- **Diff**:
  ```python
  <<<< REMOVE (lines 28-32)
  try:
      from pydantic import BaseModel, Field
      _HAY_PYDANTIC = True
  except ImportError:
      _HAY_PYDANTIC = False
  ====
  (completely remove)
  >>>>
  ```
  ```python
  <<<< REMOVE (lines 190-204)
  if _HAY_PYDANTIC:
      class StyleDNA(BaseModel):
          medium: str = Field(description="Artistic medium and rendering technique")
          ...
      class CharacterAnchors(BaseModel):
          name: str = Field(description="Character identifier")
          anchors_block: str = Field(description="Immutable physical visual anchors (~20-40 words)")
  ====
  (completely remove)
  >>>>
  ```

---

### Change 2: Harden `describir_paleta_hex`
- **Target**: Lines 262-287
- **Before**:
  ```python
  def describir_paleta_hex(hex_list: list[str]) -> str:
      """Mapea una lista de códigos hex a nombres en inglés naturales por distancia euclídea."""
      nombres = []
      vistos = set()
      for h in hex_list:
          h_clean = h.strip().lstrip("#")
          if len(h_clean) != 6:
              continue
  ```
- **After**:
  ```python
  def describir_paleta_hex(hex_list: list[str]) -> str:
      """Mapea una lista de códigos hex a nombres en inglés naturales por distancia euclídea."""
      if not isinstance(hex_list, (list, tuple)):
          return "balanced color palette"
      nombres = []
      vistos = set()
      for h in hex_list:
          if not isinstance(h, str):
              continue
          h_clean = h.strip().lstrip("#")
          if len(h_clean) != 6:
              continue
  ```

---

### Change 3: Harden `inferir_preset_id`
- **Target**: Lines 301-310
- **Before**:
  ```python
          datos = leer_json(p_path, por_defecto={})
          base = os.path.basename(ruta_lamina)
          for pr in datos.get("presets", []):
              refs = pr.get("datos", {}).get("estilo", {}).get("referencias", [])
              for r in refs:
                  if base == os.path.basename(r):
                      return pr.get("id")
  ```
- **After**:
  ```python
          datos = leer_json(p_path, por_defecto={})
          if isinstance(datos, dict):
              base = os.path.basename(ruta_lamina)
              presets = datos.get("presets")
              if isinstance(presets, list):
                  for pr in presets:
                      if not isinstance(pr, dict):
                          continue
                      datos_pr = pr.get("datos") if isinstance(pr.get("datos"), dict) else {}
                      estilo_pr = datos_pr.get("estilo") if isinstance(datos_pr.get("estilo"), dict) else {}
                      refs = estilo_pr.get("referencias")
                      if isinstance(refs, list):
                          for r in refs:
                              if isinstance(r, str) and base == os.path.basename(r):
                                  return pr.get("id")
  ```

---

### Change 4: Harden `sintetizar_adn_desde_preset` against Null and Non-String Values
- **Target**: Lines 331-390
- **Before**:
  ```python
      guia = preset_encontrado.get("datos", {}).get("estilo", {}).get("guia", {})
      if not guia:
          return copy.deepcopy(DEFAULT_STYLE_DNA)

      # 1. Medium
      acabado = guia.get("acabado", "").strip()
      if acabado:
          medium = acabado.split(".")[0].strip()
      else:
          guia_txt = guia.get("guia", "").strip()
          medium = guia_txt.split(".")[0].strip() if guia_txt else DEFAULT_STYLE_DNA["medium"]

      # 2. Palette hex
      paleta_raw = guia.get("paleta", [])
      palette_hex = []
      if isinstance(paleta_raw, list):
          for h in paleta_raw:
              if isinstance(h, str):
                  h_clean = h.strip()
                  if not h_clean.startswith("#"):
                      h_clean = "#" + h_clean
                  if re.match(r"^#[0-9a-fA-F]{6}$", h_clean):
                      palette_hex.append(h_clean)
      if not palette_hex:
          palette_hex = list(DEFAULT_STYLE_DNA["palette_hex"])

      # 3. Palette desc
      palette_desc = describir_paleta_hex(palette_hex)

      # 4. Linework
      trazo = guia.get("trazo", "").strip()
      linework = trazo.split(".")[0].strip() if trazo else DEFAULT_STYLE_DNA["linework"]

      # 5. Texture
      relleno = guia.get("relleno", "").strip()
      texture = relleno.split(".")[0].strip() if relleno else DEFAULT_STYLE_DNA["texture"]

      # 6. Lighting style
      luz = guia.get("luz", "").strip()
      lighting_style = luz.split(".")[0].strip() if luz else DEFAULT_STYLE_DNA["lighting_style"]

      # 7. Negative style
      evitar_raw = guia.get("evitar", "")
      negative_style = ""
      if isinstance(evitar_raw, list):
          negative_style = ", ".join(str(x).strip() for x in evitar_raw if x)
      elif isinstance(evitar_raw, str):
          evitar_str = evitar_raw.strip()
          if evitar_str.startswith("[") and evitar_str.endswith("]"):
              try:
                  items = ast.literal_eval(evitar_str)
                  if isinstance(items, list):
                      negative_style = ", ".join(str(x).strip() for x in items if x)
              except Exception:
                  negative_style = re.sub(r"[\[\]'\"\n]", "", evitar_str).strip()
          else:
              negative_style = evitar_str
      if not negative_style:
          negative_style = DEFAULT_STYLE_DNA["negative_style"]
  ```
- **After**:
  ```python
      datos_pr = preset_encontrado.get("datos") if isinstance(preset_encontrado.get("datos"), dict) else {}
      estilo_pr = datos_pr.get("estilo") if isinstance(datos_pr.get("estilo"), dict) else {}
      guia = estilo_pr.get("guia") if isinstance(estilo_pr.get("guia"), dict) else {}
      if not guia:
          return copy.deepcopy(DEFAULT_STYLE_DNA)

      # 1. Medium
      raw_acabado = guia.get("acabado")
      acabado = raw_acabado.strip() if isinstance(raw_acabado, str) else ""
      if acabado:
          medium = acabado.split(".")[0].strip()
      else:
          raw_guia = guia.get("guia")
          guia_txt = raw_guia.strip() if isinstance(raw_guia, str) else ""
          medium = guia_txt.split(".")[0].strip() if guia_txt else DEFAULT_STYLE_DNA["medium"]
      if not medium:
          medium = DEFAULT_STYLE_DNA["medium"]

      # 2. Palette hex
      paleta_raw = guia.get("paleta")
      palette_hex = []
      if isinstance(paleta_raw, list):
          for h in paleta_raw:
              if isinstance(h, str):
                  h_clean = h.strip()
                  if not h_clean.startswith("#"):
                      h_clean = "#" + h_clean
                  if re.match(r"^#[0-9a-fA-F]{6}$", h_clean):
                      palette_hex.append(h_clean)
      if not palette_hex:
          palette_hex = list(DEFAULT_STYLE_DNA["palette_hex"])

      # 3. Palette desc
      palette_desc = describir_paleta_hex(palette_hex) or DEFAULT_STYLE_DNA["palette_desc"]

      # 4. Linework
      raw_trazo = guia.get("trazo")
      trazo = raw_trazo.strip() if isinstance(raw_trazo, str) else ""
      linework = trazo.split(".")[0].strip() if trazo else DEFAULT_STYLE_DNA["linework"]
      if not linework:
          linework = DEFAULT_STYLE_DNA["linework"]

      # 5. Texture
      raw_relleno = guia.get("relleno")
      relleno = raw_relleno.strip() if isinstance(raw_relleno, str) else ""
      texture = relleno.split(".")[0].strip() if relleno else DEFAULT_STYLE_DNA["texture"]
      if not texture:
          texture = DEFAULT_STYLE_DNA["texture"]

      # 6. Lighting style
      raw_luz = guia.get("luz")
      luz = raw_luz.strip() if isinstance(raw_luz, str) else ""
      lighting_style = luz.split(".")[0].strip() if luz else DEFAULT_STYLE_DNA["lighting_style"]
      if not lighting_style:
          lighting_style = DEFAULT_STYLE_DNA["lighting_style"]

      # 7. Negative style
      evitar_raw = guia.get("evitar")
      negative_style = ""
      if isinstance(evitar_raw, list):
          tokens = [str(x).strip() for x in evitar_raw if x is not None and str(x).strip()]
          negative_style = ", ".join(tokens)
      elif isinstance(evitar_raw, str):
          evitar_str = evitar_raw.strip()
          if evitar_str.startswith("[") and evitar_str.endswith("]"):
              try:
                  items = ast.literal_eval(evitar_str)
                  if isinstance(items, list):
                      tokens = [str(x).strip() for x in items if x is not None and str(x).strip()]
                      negative_style = ", ".join(tokens)
              except Exception:
                  negative_style = re.sub(r"[\[\]'\"\n]", "", evitar_str).strip()
          else:
              negative_style = evitar_str
      if not negative_style or not negative_style.strip():
          negative_style = DEFAULT_STYLE_DNA["negative_style"]
  ```

---

### Change 5: Add Character Validation Helper `_son_anclas_validas`
- **Target**: Place immediately after `_es_adn_valido` (~line 424)
- **Code**:
  ```python
  def _son_anclas_validas(data: Optional[dict]) -> bool:
      """Verifica que un diccionario cumpla estrictamente con el contrato de Character Anchors."""
      if not isinstance(data, dict):
          return False
      name = data.get("name")
      anchors_block = data.get("anchors_block")
      if not isinstance(name, str) or not name.strip():
          return False
      if not isinstance(anchors_block, str) or not anchors_block.strip():
          return False
      return True
  ```

---

### Change 6: Harden `_ancla_fallback` and Character Cache in `extraer_anclas_personaje`
- **Target**: Lines 620-643 and line 660
- **Before**:
  ```python
      nombre = str(nombre_personaje).strip() if nombre_personaje else "character"

      def _ancla_fallback():
          desc = descripcion_fallback.strip() if descripcion_fallback else ""
          if desc:
              anchors_block = f"the character {nombre}, {desc}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
          else:
              anchors_block = f"the character {nombre}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
          return {"name": nombre, "anchors_block": anchors_block}
  ...
          if os.path.isfile(cache_h):
              data = leer_json(cache_h)
              if isinstance(data, dict) and "name" in data and "anchors_block" in data:
                  return data
  ...
          if anclas and "name" in anclas and "anchors_block" in anclas and anclas["anchors_block"]:
              _guardar_cache_huella("personaje", ruta_personaje, anclas)
              return anclas
  ```
- **After**:
  ```python
      nombre = str(nombre_personaje).strip() if (nombre_personaje is not None and str(nombre_personaje).strip()) else "character"

      def _ancla_fallback():
          desc = descripcion_fallback.strip() if isinstance(descripcion_fallback, str) else ""
          if desc:
              anchors_block = f"the character {nombre}, {desc}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
          else:
              anchors_block = f"the character {nombre}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
          return {"name": nombre, "anchors_block": anchors_block}
  ...
          if os.path.isfile(cache_h):
              data = leer_json(cache_h)
              if _son_anclas_validas(data):
                  return data
  ...
          if _son_anclas_validas(anclas):
              _guardar_cache_huella("personaje", ruta_personaje, anclas)
              return anclas
  ```

---

## 5. Verification Method

To verify these changes independently:

1. **Verify `describir_paleta_hex` defensive handling**:
   ```bash
   python3 -c "import pasos.inversion_visual as iv; assert isinstance(iv.describir_paleta_hex([None, 123, '#FF0000', True]), str)"
   ```
   *Expected*: Passes silently without `AttributeError`.

2. **Verify `sintetizar_adn_desde_preset` null-safety**:
   ```bash
   python3 -c "
   import pasos.inversion_visual as iv
   from unittest.mock import patch
   with patch('pasos.inversion_visual.leer_json') as m:
       m.return_value = {'presets': [{'id': 'pr_null', 'datos': {'estilo': {'guia': {'acabado': None, 'guia': None, 'paleta': None, 'trazo': None, 'relleno': None, 'luz': None, 'evitar': None}}}}]}
       dna = iv.sintetizar_adn_desde_preset('pr_null')
       assert isinstance(dna, dict) and dna['medium'] and dna['palette_desc']
   "
   ```
   *Expected*: Passes silently without `AttributeError`.

3. **Verify `_ancla_fallback` non-string handling**:
   ```bash
   python3 -c "import pasos.inversion_visual as iv; c = iv.extraer_anclas_personaje('/nonexistent.png', 'Marcus', descripcion_fallback=12345); assert isinstance(c, dict) and c['name'] == 'Marcus'"
   ```
   *Expected*: Passes silently without `AttributeError`.

4. **Verify Stress Test Suite passes**:
   ```bash
   python3 -m unittest tests/test_stress_inversion_visual.py -v
   ```
   *Expected*: `test_stress_24`, `test_stress_27`, `test_stress_29`, and `test_stress_30` all PASS.
