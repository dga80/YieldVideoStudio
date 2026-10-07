# Handoff Report: Style & Character DNA Caching, Persistence & Filesystem Integration

**Agent**: `teamwork_preview_explorer_m1_2`  
**Milestone**: M1 (Visual Style & Character DNA Inversion)  
**Target Recipient**: Orchestrator (`parent` / `9b5a6257-25d0-4e41-8283-7957c59e0602`) and M1 Implementer  

---

## 1. Observation

1. **Preset Directory Layout & Contents**:
   - `banco/presets/` contains four active preset folders:
     - `pr1a0eef81dc7`: `miniatura.png` (1920x1620, RGB, 1,875,663 bytes), `00_cara.png` through `05_diagrama.png` (1376x768 RGB, 118,003 to 830,404 bytes).
     - `pr1a0f81fbf25`: `miniatura.png` (1920x1620, RGB, 2,852,434 bytes), `00_cara.png` (3000x4000 RGBA, 6,390,858 bytes), `01_cuerpos.png` (240x240 RGB), `02_interior.png` (348x348 Palette/P, 20,606 bytes).
     - `pr1a0f91a4e44`: `miniatura.png` (1920x1620, RGB, 2,575,732 bytes), files named `00_00_00_00_00_cara.png` through `05_05_05_05_05_diagrama.png` (300-1367 px RGB).
     - `pr1a10889874e`: `miniatura.png` (1920x1620, RGB, 2,972,613 bytes), `00_cara.png` (2816x1536, 4,355,245 bytes), etc.
   - `presets.json` lines 1-480 define these presets. In `datos.estilo.referencias`, each preset references its exact image paths in `banco/presets/{preset_id}/`. Each preset also contains a `guia` dict with `guia`, `paleta`, `trazo`, `relleno`, `luz`, `acabado`, and `evitar`.
   - No `dna_estilo.json` currently exists in any of the `banco/presets/{preset_id}/` directories (`find_by_name` returned 0 matches).

2. **Cast Sheet Layout & Emergency Canvases**:
   - Cast sheets are stored in project folders at `proyectos/<proyecto>/pasos/assets/v{N}/assets/reparto/{nombre}.png`.
   - Inspection of `que_pasaria_si_la_humanidad_dejara_de_morir_durante_24_horas/pasos/assets/v1/assets/reparto/`:
     - `criminales.png`: 1024x576 RGBA, 197,866 bytes (legitimate cast sheet).
     - `ejecutivos.png`, `medicos.png`, `pacientes.png`, `gente_generica.png`: ~12 KB each (emergency canvas placeholders).
   - In `test_pluma_auto/pasos/assets/v1/assets/reparto/`:
     - `gente.png`: 1024x576 RGBA, 178,578 bytes (legitimate).
     - `pastor.png`: 1280x720 RGBA, 10,377 bytes (emergency canvas).

3. **Core Filesystem and Hashing Utilities**:
   - `nucleo/proyecto.py:228`: `huella(valor)` calculates SHA-256 hex truncated to 16 characters.
   - `nucleo/proyecto.py:241`: `escribir_json(ruta, datos)` performs atomic write via `tempfile.mkstemp` and `os.replace` guarded by `lock_de(ruta)`.
   - `pasos/medios.py:1268`: `huella_fichero(ruta, bloque=1 << 20)` computes a streaming SHA-256 hash (16-char hex) of any disk file.
   - `pasos/medios.py:39`: `medios.BANCO` defaults to `<RAIZ_ESTUDIO>/banco`.

4. **Integration Points in `pasos/p6_assets.py`**:
   - Line 4279: `_exigir_estilo(p)` validates style references and style guide presence.
   - Lines 3741-3780: `_referencias_estilo(p, cache, escena=None)` generates/normalizes `lamina_estilo_{firma}.png` using `hashlib.sha1`.
   - Lines 4347-4363: Assets generation loop writes character sheets to `dirs["reparto"]/{ficha['nombre']}.png`.
   - Lines 3879-3892: `_referencias_escena` loads character sheets `hoja = os.path.join(dirs["reparto"], f"{personaje}.png")`.
   - Lines 2815-2860: `_prompt_reparto` includes phantom reference line 2830: `"Reference image 1 is a STYLE SHEET: copy the drawing style it shows..."`.
   - Lines 2590-2640: `_prompt_completo` includes phantom reference lines 2596: `"Reference image {indice} is a STYLE SHEET: ..."` and 2344: `"Reference image {indice} is the cast sheet for '{ref['nombre']}': ..."`.

5. **Gemini Vision Engine**:
   - `pasos/gemini_cliente.py` is present and functional.
   - `gemini_cliente.hay_gemini()` returns `True`, with a valid `GEMINI_API_KEY` configured in `secretos/.env`.
   - `gemini_cliente._construir_partes` automatically converts image files into base64 `inline_data` objects, auto-resizing down to 1024 px.

---

## 2. Logic Chain

1. **Preset Style DNA Persistence** (supported by Observations 1 & 3):
   - Presets in `banco/presets/{preset_id}/` are global, reused across many video projects, and do not change unless edited.
   - Therefore, saving inverted style DNA to `banco/presets/{preset_id}/dna_estilo.json` guarantees that subsequent video generations under that preset read the pre-computed DNA in `< 1ms` with zero external API calls.
   - Using `nucleo.proyecto.escribir_json` ensures writes are atomic, preventing corrupt JSON files during parallel runs.

2. **Ad-Hoc / Standalone Style DNA Fallback** (supported by Observations 1, 3 & 4):
   - When a project uses custom reference images without a `preset_id`, `p6_assets.py` creates `lamina_estilo_{firma}.png`.
   - The file content hash `medios.huella_fichero(ruta_lamina)` provides a deterministic identifier.
   - Caching at `banco/dna/estilo_{huella}.json` (and locally at `dirs["cache"]/lamina_estilo_{firma}_dna.json`) enables cross-project and cross-run deduplication.

3. **Character DNA Caching Strategy** (supported by Observations 2 & 3):
   - Cast sheets are generated per project and written to `dirs["reparto"]/{nombre}.png`.
   - Their visual identity is tied to the generated pixels.
   - Using `medios.huella_fichero(ruta_personaje)` yields a content-addressed key `huella`.
   - Saving to `banco/dna/personaje_{huella}.json` (and sidecar `{nombre}.dna.json`) ensures that if a character sheet is preserved or reused across versions (`v1` -> `v2`), its textual anchors are never re-extracted.

4. **Emergency Canvas Guard** (supported by Observation 2):
   - We observed that 12 KB emergency canvas placeholders frequently exist in `assets/reparto/` due to upstream network or credit timeouts.
   - If an emergency canvas were sent to Gemini Vision, it would extract descriptors of a black box or gold border rather than the character.
   - Therefore, `extraer_anclas_personaje` must detect files `< 20 KB` and immediately fall back to `ficha.get("descripcion")` without calling the vision API.

5. **Filesystem Integration in `p6_assets.py`** (supported by Observation 4):
   - Calling `extraer_adn_estilo` at step initialization (`ejecutar` line 4279) stores the DNA block into `p["estilo"]["adn"]`.
   - Calling `extraer_anclas_personaje` immediately after a cast sheet is generated (line 4358) and during scene reference resolution (`_referencias_escena` line 3881) provides anchor strings for the prompt builder.
   - In M2, this allows replacing lines 2830 and 2596 with modular slots `[STYLE DNA]` and `[CHARACTER ANCHORS]`.

---

## 3. Caveats

- **No Active `dna_estilo.json` Files Exist Yet**: All presets currently lack `dna_estilo.json`. The first run of each preset will perform an extraction and persist it to disk.
- **Heterogeneous Image Modes**: Preset `pr1a0f81fbf25` contains a 3000x4000 RGBA image and a 20 KB palette-indexed (P mode) image. Any code processing preset images directly with PIL must convert to RGB (`im.convert("RGB")`).
- **Network / Offline Mode**: If Gemini API is unreachable, `extraer_adn_estilo` must have an offline fallback to synthesize DNA from `presets.json` `guia` dictionary fields (`paleta`, `trazo`, `relleno`, etc.), ensuring tests pass even without network access.

---

## 4. Conclusion

The disk layout and persistence architecture for M1 is well-defined, minimal, and fully compatible with existing project conventions:

1. **Preset Style DNA**:
   - Path: `banco/presets/{preset_id}/dna_estilo.json`
   - Content: Exact schema specified in `PROJECT.md` (`medium`, `palette_hex`, `palette_desc`, `linework`, `texture`, `lighting_style`, `negative_style`, `dna_block`).
2. **Standalone Style DNA**:
   - Path: `banco/dna/estilo_{huella}.json` where `huella = medios.huella_fichero(ruta_lamina)`.
3. **Character DNA**:
   - Path: `banco/dna/personaje_{huella}.json` where `huella = medios.huella_fichero(ruta_personaje)`.
   - Sidecar: `dirs["reparto"]/{nombre}.dna.json`.
   - Guard: Files `< 20 KB` bypass vision API and use textual description fallback.
4. **Integration Points**:
   - `pasos/p6_assets.py`: `ejecutar()` initializes Style DNA; `_prompt_reparto()` uses Style DNA; cast loop extracts Character Anchors; `_referencias_escena()` binds anchors to scene references.

---

## 5. Verification Method

To independently verify:

1. **Inspect preset files and directory permissions**:
   ```bash
   python3 -c '
   import os, json
   from nucleo.proyecto import leer_json
   presets = leer_json("presets.json")["presets"]
   for p in presets:
       pid = p["id"]
       path = f"banco/presets/{pid}"
       assert os.path.isdir(path), f"Missing {path}"
       print(f"Preset {pid} ({p[\"nombre\"]}) OK: {len(os.listdir(path))} files")
   '
   ```
2. **Verify hashing and atomic write mechanisms**:
   ```bash
   python3 -c '
   import os
   from nucleo.proyecto import escribir_json, leer_json
   from pasos import medios
   test_file = "banco/presets/pr1a0eef81dc7/00_cara.png"
   h = medios.huella_fichero(test_file)
   assert len(h) == 16, f"Invalid hash length {h}"
   print("huella_fichero OK:", h)
   '
   ```
3. **Verify Gemini API readiness**:
   ```bash
   python3 -c '
   from pasos import gemini_cliente
   assert gemini_cliente.hay_gemini() is True
   print("Gemini API Key OK")
   '
   ```
4. **Invalidation condition**:
   If a preset image in `banco/presets/{preset_id}/` has modification time newer than `dna_estilo.json`, or if `rehacer=True` is requested, the cache is invalidated and regenerated.
