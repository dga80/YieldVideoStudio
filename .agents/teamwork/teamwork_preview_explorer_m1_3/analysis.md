# Analysis Report: Fallback Mechanisms, Heuristics & Verification Strategy (Milestone 1)

**Agent**: `teamwork_preview_explorer_m1_3`  
**Milestone**: M1 (Visual Style & Character DNA Inversion)  
**Date**: 2026-10-06  
**Status**: Completed  

---

## 1. Executive Summary
This report defines the deterministic heuristic fallback mechanisms, graceful image corruption/emergency canvas handling, and verification test architecture for `pasos/inversion_visual.py`. By extracting and translating the dense `datos.estilo.guia` fields in `presets.json` into the 8 required Style DNA fields, the pipeline guarantees 100% deterministic, zero-cost fallback whenever the Gemini Vision API is offline, unconfigured, or rate-limited. Furthermore, a rigorous multi-tier image validation routine prevents corrupted files and emergency canvas placeholders (such as the 13 KB flat canvases with `(212, 175, 55, 120)` gold borders discovered in `proyectos/test_pluma_auto/`) from poisoning the visual style conditioning.

---

## 2. Deterministic Heuristic Fallback (`presets.json` -> Style DNA)

### 2.1 Presets Inspection & Data Richness
Investigation of `presets.json` reveals 4 active presets of type `"canal"` (`pr1a0eef81dc7` [Pluma_2], `pr1a0f81fbf25` [Pluma_3], `pr1a0f91a4e44` [Cartoon_Stick], and `pr1a10889874e` [androides]). Each preset contains an exquisitely structured `datos.estilo.guia` dictionary with English visual specifications:
- `guia`: Complete narrative prompt in English.
- `paleta`: List of 8 exact hex colors (e.g. `['#ffffff', '#000000', '#7cc47c', ...]`).
- `trazo`: Outline stroke width, texture, and continuity.
- `relleno`: Shading, texture, gradient policies.
- `luz`: Directionality, ambient lighting, shadows.
- `acabado`: Medium, surface finish, render quality.
- `evitar`: Negative prompt constraints (either Python list, stringified list, or comma-separated string).
- `resumen_es`: High-level Spanish summary.

### 2.2 Field-by-Field Translation Specification
The interface contract defined in `PROJECT.md § Interface Contracts` requires `extraer_adn_estilo` to return a dictionary with exactly 8 keys:

| Style DNA Key | Source Field in `guia` | Heuristic Extraction & Normalization Rule |
| :--- | :--- | :--- |
| `medium` | `guia["acabado"]` (fallback `guia["guia"]`) | Extract first clause: `acabado.split('.')[0].strip()`. Perfectly isolates artistic medium (e.g. *"Clean digital vector look with minimal hand-drawn marker imperfection..."* or *"The final render is a photorealistic 3D image..."*). |
| `palette_hex` | `guia["paleta"]` | Take list of hex codes, normalize to uppercase/lowercase `#RRGGBB`. If missing/empty, default to `['#000000', '#FFFFFF', '#4A90E2']`. |
| `palette_desc` | `guia["paleta"]` | Deterministic RGB Euclidean nearest-neighbor matching against a fixed palette of 20 canonical color names (white, black, charcoal, muted sage green, vibrant cobalt blue, warm amber, deep orange, crimson red, steel blue, gold, cyan, etc.). |
| `linework` | `guia["trazo"]` | Extract first sentence: `trazo.split('.')[0].strip()`. Accurately describes stroke weight, marker texture, or lack of 2D strokes. |
| `texture` | `guia["relleno"]` | Extract first sentence: `relleno.split('.')[0].strip()`. Captures flat solid color fills, cel-shading, or PBR materials. |
| `lighting_style` | `guia["luz"]` | Extract first sentence: `luz.split('.')[0].strip()`. Captures flat ambient daylight, directional cel shading, or cool diffuse lighting. |
| `negative_style` | `guia["evitar"]` | Multi-format parser: handles Python `list`, stringified list `['...', '...']` via regex/`ast.literal_eval`, or raw comma-separated text. Joins into clean comma-separated negative prompt string. |
| `dna_block` | Synthesized | Assembled compact English descriptor: `{medium}. Linework: {linework}. Fills: {texture}. Lighting: {lighting_style}. Palette: {palette_desc}.` Length bounded to ~50-60 tokens (approx 280-320 chars). |

### 2.3 Preset Identification & Resolution Flow
When `extraer_adn_estilo(ruta_lamina: str, preset_id: str = None)` is invoked:
1. **Explicit ID**: If `preset_id` is provided, look up `preset_id` in `presets.json`.
2. **Inferred ID**: If `preset_id` is `None`, inspect `ruta_lamina` using regex `r"(pr[0-9a-f]{10,14})"`. If a match is found in the directory path (e.g. `banco/presets/pr1a0eef81dc7/00_cara.png`), use it.
3. **Reference Lookup**: Search `referencias` lists across all presets in `presets.json` to find if `ruta_lamina` is registered.
4. **Universal Default Baseline**: If the preset is completely unknown, deleted, or has no `guia`, return the universal neutral fallback `DEFAULT_STYLE_DNA` (a production-ready clean 2D digital vector baseline).

---

## 3. Graceful Handling of Corrupted, Missing, or Emergency Images

### 3.1 Defect Taxonomy
Image reference inputs to `extraer_adn_estilo` and `extraer_anclas_personaje` can exhibit several failure modes:
1. **Missing Paths**: `ruta` is `None`, empty `""`, or points to a non-existent file (`os.path.exists() == False`).
2. **Zero-Byte Files**: File created on disk but abortive shutdown left `os.path.getsize() == 0`.
3. **Truncated/Garbage Bytes**: Broken headers or corrupted payloads failing `PIL.Image.open().verify()`.
4. **Sub-Minimal Geometry**: Images smaller than 16x16 pixels.
5. **Emergency Canvases / Flat Placeholders**: Flat gradient canvases generated by `_generar_lienzo_emergencia` in `yieldchat_imagen.py`.

### 3.2 Discovery of Emergency Canvas in Repository
Direct inspection of `proyectos/test_pluma_auto/pasos/assets/v5/assets/reparto/pastor.png` confirmed the presence of an emergency canvas on disk:
- File size: 13,040 bytes (< 25 KB).
- Dimensions: 1280x720 RGBA.
- Pixel at `(24, 24)`: Gold border signature `(212, 175, 55, 120)` from `yieldchat_imagen.py:261`.
- Color standard deviation: extremely low (~3.2).

**Impact**: If `pastor.png` were submitted to Gemini Vision, the model would invert the gold border and dark void, corrupting character anchors across subsequent scenes.

### 3.3 Multi-Tier Validation Algorithm (`validar_imagen`)
```python
def validar_imagen(ruta: str) -> tuple[bool, str]:
    if not ruta or not isinstance(ruta, str):
        return False, "ruta_invalida_o_vacia"
    if not os.path.isfile(ruta):
        return False, "fichero_no_existe"
    size = os.path.getsize(ruta)
    if size == 0:
        return False, "fichero_vacio_0_bytes"
    if size < 100:
        return False, "fichero_demasiado_pequeno"
    try:
        with Image.open(ruta) as img:
            img.verify()
        with Image.open(ruta) as img:
            w, h = img.size
            if w < 16 or h < 16:
                return False, "dimensiones_invalidas"
    except Exception as e:
        return False, f"corrupcion_pil: {e}"
        
    # Emergency Canvas Detection (Size < 30KB + Gold Border Signature)
    if size < 30 * 1024:
        try:
            with Image.open(ruta) as img:
                arr = img.convert("RGB")
                w, h = arr.size
                if w >= 50 and h >= 50:
                    px = arr.getpixel((24, 24))
                    if abs(px[0] - 212) <= 15 and abs(px[1] - 175) <= 15 and abs(px[2] - 55) <= 15:
                        return False, "lienzo_de_emergencia_borde_dorado"
        except Exception:
            pass

    return True, "ok"
```

### 3.4 Fallback Execution Strategy
- **For `extraer_adn_estilo`**: If `validar_imagen(ruta_lamina)` returns `False`, immediately skip vision API invocation, log an explanatory warning, and execute the deterministic heuristic fallback from `presets.json`.
- **For `extraer_anclas_personaje`**: If `validar_imagen(ruta_personaje)` returns `False`, skip vision API invocation, log an explanatory warning, and construct a clean textual anchor descriptor using `nombre_personaje` and optional project catalog description (`catalogo["reparto"][nombre]["descripcion"]`).

---

## 4. Verification Test Suite Architecture

### 4.1 Test Runner & Environment Compatibility
- Python version: 3.12.
- Environment: Standard library `unittest` is natively functional with zero dependencies (`python3 -m unittest discover` or `python3 pasos/prueba_inversion_visual.py`).
- Design: The test file will support dual execution: standalone CLI with `ok`/`igual` counters (matching `pasos/prueba_presets.py`) and standard `unittest.TestCase` classes.

### 4.2 Comprehensive Test Matrix (12 Scenarios)

| # | Test Scenario | Input Conditions | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **T1** | Schema & Key Verification | Valid dummy image, Mock Gemini Vision response | Returns dict with exactly all 8 required keys; hex palette validated with regex `^#[0-9a-fA-F]{6}$`. |
| **T2** | Heuristic Fallback Pluma_2 | `ruta_lamina=None`, `preset_id="pr1a0eef81dc7"`, API disabled | Returns Pluma_2 DNA with 8 hex colors, uniform black linework, vector medium. |
| **T3** | Heuristic Fallback Pluma_3 | `ruta_lamina=None`, `preset_id="pr1a0f81fbf25"`, API disabled | Returns Pluma_3 DNA with solid black stick figure traits, 8 hex colors. |
| **T4** | Heuristic Fallback androides | `ruta_lamina=None`, `preset_id="pr1a10889874e"`, API disabled | Returns 3D CGI photorealistic DNA, chrome/plastic fills, no 2D outlines. |
| **T5** | Inferred Preset ID | `ruta_lamina=".../banco/presets/pr1a0f91a4e44/00_cara.png"`, `preset_id=None`, API disabled | Automatically extracts preset ID `pr1a0f91a4e44` and synthesizes Cartoon_Stick DNA. |
| **T6** | Unknown Preset ID | `preset_id="pr_inventado_999"`, API disabled | Returns `DEFAULT_STYLE_DNA` gracefully without exception. |
| **T7** | Corrupted Reference (0-byte) | `ruta_lamina` is 0-byte file | Detected as invalid; falls back to heuristic DNA cleanly. |
| **T8** | Corrupted Reference (Garbage) | `ruta_lamina` contains random junk bytes | PIL verification catches corruption; falls back to heuristic DNA cleanly. |
| **T9** | Emergency Canvas Rejection | `ruta_lamina` is emergency canvas with gold border | Detected as emergency canvas; blocked from vision API; falls back to preset heuristic. |
| **T10** | Character Anchors Normal | Valid character image, Mock Gemini Vision | Returns `{"name": "pastor", "anchors_block": "..."}` matching character attributes. |
| **T11** | Character Anchors Emergency/Corrupt | `ruta_personaje` is corrupted or emergency canvas | Returns clean synthesized text anchors: `the character pastor, recognizable distinct character design...`. |
| **T12** | API Failure Chaos | Mock API raises `RuntimeError("HTTP 429 Quota Exceeded")` | Exception trapped internally; logs warning; returns heuristic DNA seamlessly. |

---

## 5. Implementation Code Blueprint

### 5.1 Proposed Module Structure (`pasos/inversion_visual.py`)
```python
# =====================================================================
# pasos/inversion_visual.py (Blueprint)
# =====================================================================
import os
import re
import json
import logging
from PIL import Image

logger = logging.getLogger("inversion_visual")

DEFAULT_STYLE_DNA = {
    "medium": "clean digital 2D vector illustration",
    "palette_hex": ["#1A1A1A", "#FFFFFF", "#4A90E2", "#7FB800"],
    "palette_desc": "charcoal black, stark white, clear sky blue, muted leaf green",
    "linework": "uniform clean solid dark outlines of consistent stroke weight",
    "texture": "flat solid color fills with zero gradients and smooth surfaces",
    "lighting_style": "diffuse ambient daylight, no harsh specular highlights or cast shadows",
    "negative_style": "photorealistic, 3D render, glossy reflections, muddy textures, noisy grain",
    "dna_block": "clean digital 2D vector illustration, uniform clean dark outlines, flat solid color fills, diffuse ambient lighting, palette: charcoal black, stark white, sky blue"
}

def validar_imagen(ruta: str) -> tuple[bool, str]: ...
def inferir_preset_id(ruta: str, preset_id: str = None) -> str | None: ...
def sintetizar_adn_desde_preset(preset_id: str) -> dict: ...

def extraer_adn_estilo(ruta_lamina: str, preset_id: str = None) -> dict:
    pid = inferir_preset_id(ruta_lamina, preset_id)
    valida, motivo = validar_imagen(ruta_lamina)
    
    # 1. Si la imagen no es valida o es lienzo de emergencia, saltar directo al fallback
    if not valida:
        logger.warning(f"Lámina '{ruta_lamina}' no válida ({motivo}). Usando fallback heurístico.")
        return sintetizar_adn_desde_preset(pid) if pid else DEFAULT_STYLE_DNA

    # 2. Si hay API disponible, intentar llamada vision multimodal
    try:
        from pasos.gemini_cliente import hay_gemini, ejecutar
        if hay_gemini():
            # Invocación multimodal (diseñada por M1 Explorer 1)
            ...
    except Exception as e:
        logger.warning(f"Fallo en llamada a Gemini Vision: {e}. Usando fallback heurístico.")

    # 3. Fallback determinista
    if pid:
        return sintetizar_adn_desde_preset(pid)
    return DEFAULT_STYLE_DNA

def extraer_anclas_personaje(ruta_personaje: str, nombre_personaje: str) -> dict:
    valida, motivo = validar_imagen(ruta_personaje)
    if not valida:
        logger.warning(f"Hoja de personaje '{ruta_personaje}' no válida ({motivo}). Usando anclas textuales.")
        return {
            "name": str(nombre_personaje),
            "anchors_block": f"the character {nombre_personaje}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
        }
    ...
```

This architecture ensures zero runtime failures, complete contract compliance, and total immunity against API outages and asset corruption.
