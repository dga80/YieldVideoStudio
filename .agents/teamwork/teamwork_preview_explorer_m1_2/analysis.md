# Analysis: Style & Character DNA Caching, Persistence, and Filesystem Integration

**Author**: `teamwork_preview_explorer_m1_2`  
**Date**: 2026-10-06  
**Milestone**: M1 (Visual Style & Character DNA Inversion)  

---

## 1. Executive Summary

Milestone 1 introduces multimodal visual inversion to replace legacy "phantom references" (`Reference image 1 is a STYLE SHEET...`) with deterministic English textual descriptors for Style DNA and Character Anchors.

To eliminate redundant vision API calls (which incur latency and potential token cost), this report defines the disk layout, persistence mechanics, and lifecycle for:
1. **Style DNA Caching**: Preset-level persistence at `banco/presets/{preset_id}/dna_estilo.json` and fallback content-hashed persistence at `banco/dna/estilo_{huella}.json`.
2. **Character DNA Caching**: Content-addressed persistence at `banco/dna/personaje_{huella}.json` keyed by image SHA-256 (`medios.huella_fichero`) with optional project-level sidecars (`{nombre}.dna.json`).
3. **Filesystem Integration in `pasos/p6_assets.py`**: Exact touchpoints for style loading in `ejecutar()`, cast generation in `_prompt_reparto()`, anchor extraction, and scene conditioning in `_referencias_escena()` / `_prompt_completo()`.

---

## 2. Existing Presets & Style Asset Inspection

### 2.1 Presets in `banco/presets/`
There are currently four presets in `banco/presets/` registered in `presets.json`:

| Preset ID | Name (`nombre`) | Miniatura Resolution | Reference Images | Notes / Edge Cases |
|---|---|---|---|---|
| `pr1a0eef81dc7` | Pluma_2 | 1920x1620 (1.88 MB) | `00_cara.png` through `05_diagrama.png` (1376x768 RGB) | Clean, uniform 1376x768 reference sizes. |
| `pr1a0f81fbf25` | Pluma_3 | 1920x1620 (2.85 MB) | `00_cara.png` (3000x4000 RGBA, 6.39 MB), `01_cuerpos.png` (240x240 RGB), `02_interior.png` (348x348 Palette/P), etc. | Heterogeneous resolutions (240x240 to 3000x4000) and color modes (`P`, `RGBA`, `RGB`). Requires PIL image normalization. |
| `pr1a0f91a4e44` | Cartoon_Stick | 1920x1620 (2.58 MB) | `00_00_00_00_00_cara.png` (404x316), `01_01_01_01_01_cuerpos.png` (1367x768), etc. | Filenames have repeated `00_00_...` prefixes from recursive copying. Reference paths in `presets.json` reflect these exact names. |
| `pr1a10889874e` | androides | 1920x1620 (2.97 MB) | `00_cara.png` (2816x1536), `01_cuerpos.png` (2816x1536), `02_interior.png` (2816x1536), `03_exterior.png` (1636x896 RGBA), etc. | High resolution assets (up to 2816x1536 RGB/RGBA). |

*Note on Deleted Preset*: A fifth preset `pr1a0eec3e48e` ("pluma_1") resides in the `papelera` list of `presets.json`.

### 2.2 Representative Image for Style Inversion
Each preset directory contains:
- `miniatura.png`: A composite 1920x1620 image summarizing characters, backgrounds, and graphic styling.
- `00_cara.png` through `05_diagrama.png`: 6 axis-specific reference images.
- `muestra1.png` through `muestra6.png`: Sample frames.

**Recommendation for `extraer_adn_estilo`**:
- When `preset_id` is supplied and `ruta_lamina` is not explicitly pointing to a specific file:
  1. Primary candidate: `os.path.join(medios.BANCO, "presets", preset_id, "miniatura.png")` (contains both character faces and style samples in high resolution).
  2. Alternative candidate: The preset's combined grid sheet built via `_lamina_estilo(referencias)`.
- When `ruta_lamina` is explicitly passed (e.g. `lamina_estilo_{firma}.png`), that image is inverted directly.

---

## 3. Style DNA Disk Layout and Caching Specification

### 3.1 Preset-Level Style DNA: `banco/presets/{preset_id}/dna_estilo.json`
For any preset in `banco/presets/{preset_id}/`:
- **File path**: `banco/presets/{preset_id}/dna_estilo.json`
- **Read Path**:
  ```python
  cache_path = os.path.join(medios.BANCO, "presets", preset_id, "dna_estilo.json")
  if os.path.exists(cache_path):
      return medios.leer_json(cache_path)
  ```
- **Write Path**:
  After multimodal extraction via Gemini Vision (or fallback), save atomically:
  ```python
  from nucleo.proyecto import escribir_json
  escribir_json(cache_path, adn_estilo)
  ```
- **Persistence Guarantees**:
  - `banco/presets/` is permanent studio infrastructure; it is never purged during project version increments (`v1` -> `v2`).
  - Presets applied across multiple videos immediately reuse `dna_estilo.json` with 0 ms extraction latency and 0 token cost.

### 3.2 Standalone / Ad-Hoc Style DNA: `banco/dna/estilo_{huella}.json`
When `preset_id` is None and style images are project-specific or dynamically composed (`lamina_estilo_{firma}.png`):
- Compute image content hash:
  `huella = medios.huella_fichero(ruta_lamina)` (16-character SHA-256 hex).
- **Cache Path**: `os.path.join(medios.BANCO, "dna", f"estilo_{huella}.json")`.
- **Secondary Local Path**: `os.path.splitext(ruta_lamina)[0] + "_dna.json"` (residing in `dirs["cache"]`).
- Atomic write ensures thread-safe and process-safe caching.

### 3.3 Style DNA JSON Schema
Conforming strictly to `PROJECT.md` Interface Contract:
```json
{
  "medium": "minimalist 2D vector animation, flat digital gouache",
  "palette_hex": ["#ffffff", "#000000", "#7cc47c", "#3a86ff", "#ffb703", "#fb8500", "#d90429", "#2b2d42"],
  "palette_desc": "stark white, deep solid black, muted sage green, electric cobalt blue, warm marigold yellow",
  "linework": "uniform 3-4px solid black vector outlines with subtle hand-drawn marker texture",
  "texture": "smooth 100% flat color fills, zero gradients, devoid of grain and paper noise",
  "lighting_style": "completely flat diffuse ambient illumination, zero directional shadows, no specular reflections",
  "negative_style": "3D render, photorealistic, complex shading, gradients, harsh shadows, bevel, glossy reflections",
  "dna_block": "Minimalist 2D vector animation. Uniform 3-4px solid black outlines with flat solid fills. Palette: #ffffff, #000000, #7cc47c, #3a86ff, #ffb703. Flat ambient lighting, no gradients, no 3D shading, clean negative space."
}
```

---

## 4. Character DNA Disk Layout and Caching Specification

### 4.1 Existing Cast Sheets Inspection
Inspection of project directories (`proyectos/*/pasos/assets/*/assets/reparto/`):
- `proyectos/que_pasaria_si_la_humanidad_dejara_de_morir_durante_24_horas/pasos/assets/v1/assets/reparto/`:
  - `criminales.png` (1024x576 RGBA, 197 KB): Valid character sheet.
  - `ejecutivos.png`, `medicos.png`, `pacientes.png`, `gente_generica.png` (~12 KB each): Emergency placeholder canvases (flat black/gold canvas).
- `proyectos/test_pluma_auto/pasos/assets/v1/assets/reparto/`:
  - `gente.png` (1024x576 RGBA, 178 KB in v1, 406 KB in v4): Valid character sheet.
  - `pastor.png` (10 KB): Emergency placeholder canvas.

### 4.2 Hash-Based Caching Mechanics
Because character sheets are generated dynamically per project, their visual appearance is tied to the generated PNG:
- **Hashing**: `huella = medios.huella_fichero(ruta_personaje)`.
- **Global Cache Path**: `os.path.join(medios.BANCO, "dna", f"personaje_{huella}.json")`.
- **Project Sidecar**: `os.path.splitext(ruta_personaje)[0] + ".dna.json"`.

### 4.3 Protection Against Emergency Placeholders
When `ruta_personaje` has file size `< 20 KB` (or fails dummy canvas checks):
- Do **not** send emergency canvases to Gemini Vision API.
- Fall back gracefully to `ficha.get("descripcion")` from `catalogo["reparto"]`.
- Return valid fallback structure:
  ```json
  {
    "name": nombre_personaje,
    "anchors_block": "character with " + descripcion_fallback
  }
  ```

### 4.4 Character Anchors JSON Schema
Conforming to `PROJECT.md`:
```json
{
  "name": "criminales",
  "anchors_block": "lean figure wearing an unbuttoned dark olive utility jacket over a slate grey crewneck, buzzed dark hair, sharp angled jaw, worn canvas messenger strap across chest"
}
```

---

## 5. Integration Points in `pasos/p6_assets.py`

### 5.1 Style Loading & DNA Extraction (`p6_assets.py:ejecutar`)
- **Current code** (lines 4279-4293):
  `_exigir_estilo(p)` verifies style references and written guide.
- **Integration**:
  ```python
  from pasos.inversion_visual import extraer_adn_estilo
  
  # 1. Resolve preset_id if present
  preset_id = (p.get("estilo") or {}).get("preset_id") or getattr(proyecto, "config", {}).get("estilo_light")
  if not preset_id:
      for r in (p.get("estilo") or {}).get("referencias") or []:
          m = re.search(r"banco[/\\]presets[/\\]([^/\\]+)", str(r))
          if m:
              preset_id = m.group(1)
              break

  # 2. Resolve style lamina path
  rutas_estilo = [r for r in medios.reubicar_todas((p.get("estilo") or {}).get("referencias") or []) if os.path.exists(r)]
  lamina_path = rutas_estilo[0] if rutas_estilo else None
  if preset_id:
      miniatura_preset = os.path.join(medios.BANCO, "presets", preset_id, "miniatura.png")
      if os.path.exists(miniatura_preset):
          lamina_path = miniatura_preset

  # 3. Extract or read cached DNA
  adn_estilo = extraer_adn_estilo(lamina_path, preset_id=preset_id)
  p["estilo"]["adn"] = adn_estilo
  ```

### 5.2 Cast Asset Prompting (`p6_assets.py:_prompt_reparto`)
- **Current code** (lines 2830-2835):
  ```python
  lineas.append("Reference image 1 is a STYLE SHEET: copy the drawing style it shows...")
  ```
- **Integration**:
  Replace phantom reference lines with `adn_estilo["dna_block"]` (or `[STYLE DNA]` slot).
  The character sheet is generated with exact medium, palette, and linework textual conditioning.

### 5.3 Character Anchor Extraction (`p6_assets.py:ejecutar`)
- **Current code** (lines 4347-4363):
  After character PNG is written to `dirs["reparto"]/{ficha['nombre']}.png`:
- **Integration**:
  ```python
  from pasos.inversion_visual import extraer_anclas_personaje
  
  anclas = extraer_anclas_personaje(destino, ficha["nombre"])
  # Store in memory and/or sidecar
  inventario_anclas[ficha["nombre"]] = anclas["anchors_block"]
  ```

### 5.4 Scene Reference Resolution (`p6_assets.py:_referencias_escena`)
- **Current code** (lines 3879-3892):
  Loads `hoja = os.path.join(dirs["reparto"], f"{personaje}.png")`.
- **Integration**:
  For each character in `escena.get("personajes")`, retrieve `extraer_anclas_personaje(hoja, personaje)["anchors_block"]`.
  Attach the anchor block to the scene reference tuple/dict so `_prompt_completo` can embed it.

### 5.5 Scene Prompt Building (`p6_assets.py:_prompt_completo`)
- **Current code** (lines 2590-2640):
  Appends `Reference image {indice} is a STYLE SHEET...` and `Reference image {indice} is the cast sheet for '{ref['nombre']}'...`.
- **Integration (prepared for M2)**:
  Supply `adn_estilo` and `anclas_personajes` into the modular 5-slot architecture:
  `[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, `[NEGATIVE PROMPT]`.

---

## 6. Verification and Fault-Tolerance Strategy

1. **Gemini Availability Check**:
   `gemini_cliente.hay_gemini()` checks for `GEMINI_API_KEY` (confirmed present in environment).
2. **Offline / Fallback Resilience**:
   If Gemini is unreachable or rate-limited:
   - For Style DNA: synthesize DNA directly from `presets.json` `guia` fields (`paleta`, `trazo`, `relleno`, `luz`, `acabado`, `evitar`).
   - For Character DNA: synthesize anchors directly from `catalogo["reparto"][nombre]["descripcion"]`.
3. **Atomic File Operations**:
   Use `nucleo.proyecto.escribir_json(ruta, datos)` which uses `tempfile.mkstemp` and `os.replace` within `lock_de(ruta)` to prevent partial writes during parallel execution.
4. **Cache Directory Auto-Creation**:
   `banco/dna/` and `banco/presets/{preset_id}/` must be ensured with `os.makedirs(..., exist_ok=True)`.
