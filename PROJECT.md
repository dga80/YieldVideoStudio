# Project: asVideoStudio Visual Fidelity & Engine Resilience

## Architecture
Modernization and overhaul of the visual generation pipeline in `asVideoStudio`:
1. **Visual Style & Character DNA Inversion** (`pasos/inversion_visual.py`):
   - Uses multimodal models (Gemini 2.5 Flash Vision) to analyze style sheets (`lamina_estilo.png`) and character sheets (`reparto/*.png`).
   - Extracts dense, deterministic English visual descriptors: artistic medium, exact hex palette, brushwork/stroke, lighting style, texture, and character visual anchors.
   - Replaces phantom textual image references ("Reference image 1") with concrete textual conditioning.
2. **Modular Diffusion Prompt Synthesizer** (`pasos/p6_assets.py`):
   - Purges 14 KB of conversational Spanish meta-rules (`reglas.json:bloque_prompt("prompt_imagen")`) and layout boilerplate that saturate text encoder (CLIP/T5) context windows.
   - Constructs a 5-slot modular English prompt: `[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, `[NEGATIVE PROMPT]`.
   - Isolates negative constraints into dedicated negative prompt parameters, keeping positive prompt strictly under 250 tokens (~1,000 characters).
3. **Resilient Base64 Engine Adapter** (`motores/imagen_openai/yieldchat_imagen.py`):
   - Removes the legacy 280-character cutoff (`prompt_resumen[:277] + "..."`) and rigid template overrides (`"chrome robot panels..."`).
   - Enforces `"response_format": "b64_json"` in Agnes AI (`agnes-image-2.1-flash`), eliminating ephemeral URL 404 drops by decoding inline base64 images directly to disk.
   - Implements provider fallback and circuit breakers (Agnes AI primary, SiliconFlow/Pollinations fallback).
   - Guards cache integrity: prevents emergency canvases (12 KB flat placeholders with gold border `(212, 175, 55, 120)`) from being cached in `banco/imagenes`.
4. **Adversarial Visual QA Judge** (`motores/calidad_visual.py`):
   - Programmatic verification via OpenCV and NumPy: zero-cost, local detection of dummy/flat canvases, Bhattacharyya histogram distance against style references, framing boundary verification (`encuadres.py`), and shot continuity.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Multimodal Style Inversion | Invert `lamina_estilo.png` / presets into dense English Style DNA via Gemini 2.5 Flash Vision | M1 | ORIGINAL_REQUEST R1 |
| 2 | Multimodal Character Inversion | Invert `reparto/*.png` cast sheets into immutable textual character anchors | M1 | ORIGINAL_REQUEST R1 |
| 3 | Style DNA Caching & Persistence | Cache extracted DNA JSON to eliminate redundant vision API calls | M1 | ORIGINAL_REQUEST R1 |
| 4 | Purge Spanish Meta-Rules | Remove 5.6k chars of conversational Spanish rules from `prompt_imagen` in `p6_assets.py` | M2 | ORIGINAL_REQUEST R2 |
| 5 | Eliminate Phantom References | Replace "Reference image 1/2" text directives with embedded DNA descriptors | M2 | ORIGINAL_REQUEST R2 |
| 6 | 5-Slot Modular Prompt Architecture | Construct `[STYLE DNA]`, `[SCENE/ACTION]`, `[CHARACTER ANCHORS]`, `[LIGHTING]`, `[NEGATIVE PROMPT]` | M2 | ORIGINAL_REQUEST R2 |
| 7 | Dedicated Negative Prompt Isolation | Route prohibitions to engine `negative_prompt` channel instead of polluting positive prompt | M2 | ORIGINAL_REQUEST R2 |
| 8 | Remove 280-Char Prompt Mutilation | Remove regex clipping to 280 chars and rigid template overrides in `yieldchat_imagen.py` | M3 | ORIGINAL_REQUEST R3 |
| 9 | Agnes AI Base64 Delivery | Enforce `"response_format": "b64_json"` in Agnes AI to eliminate ephemeral 404 drops | M3 | ORIGINAL_REQUEST R3 |
| 10 | Provider Fallback & Circuit Breaker | Resilient failover with error classification (e.g. 402, 429) across engine backends | M3 | ORIGINAL_REQUEST R3 |
| 11 | Cache Pollution Prevention | Block emergency canvases (`(212, 175, 55, 120)` border / <20KB) from being written to `banco/imagenes` | M3 | ORIGINAL_REQUEST R3 |
| 12 | Dummy Canvas Detector | Detect emergency/corrupt canvases using color entropy and specific border signatures | M4 | ORIGINAL_REQUEST QA |
| 13 | Histogram & Palette Consistency Judge | Compute Bhattacharyya distance in HSV/Lab color space between generated image and preset reference | M4 | ORIGINAL_REQUEST QA |
| 14 | Framing & Continuity Verification | Verify aspect ratio, framing compliance (`encuadres.py`), and consecutive shot luminance continuity | M4 | ORIGINAL_REQUEST QA |
| 15 | E2E Integration & Verification | Validate full pipeline end-to-end against all acceptance criteria (100% tests pass) | M5 | ORIGINAL_REQUEST Acceptance |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Visual Style & Character DNA Inversion | Implement `pasos/inversion_visual.py` and integration in preset/cast loading | none | COMPLETED |
| M2 | Modular Diffusion Prompt Synthesizer | Refactor `pasos/p6_assets.py` to produce clean 5-slot English prompts (<250 tokens) | M1 | COMPLETED |
| M3 | Resilient Base64 Engine Adapter | Refactor `motores/imagen_openai/yieldchat_imagen.py` for b64_json, no truncation, cache guard | none | COMPLETED |
| M4 | Adversarial Visual QA Judge | Implement `motores/calidad_visual.py` with OpenCV histogram and dummy detection | none | COMPLETED |
| M5 | E2E Integration & Verification | Full end-to-end integration, passing 100% of E2E test suite (T1-T4) + adversarial hardening (T5) | M1, M2, M3, M4 | COMPLETED |

---

## Interface Contracts

### `pasos/inversion_visual.py` ↔ `pasos/p6_assets.py`
```python
def extraer_adn_estilo(ruta_lamina: str, preset_id: str = None) -> dict:
    """
    Returns:
    {
        "medium": str,          # e.g., "minimalist 2D vector animation, flat digital gouache"
        "palette_hex": list[str],# e.g., ["#F8F8F8", "#82C872", "#4A90E2"]
        "palette_desc": str,    # e.g., "cream white, muted moss green, soft cobalt blue"
        "linework": str,        # e.g., "clean thin vector linework, consistent stroke weight"
        "texture": str,         # e.g., "smooth flat fills, subtle grain texture"
        "lighting_style": str,  # e.g., "diffuse ambient daylight, no harsh specular highlights"
        "negative_style": str,  # e.g., "3D render, photorealistic, harsh gradients, glossy reflection"
        "dna_block": str        # Pre-assembled ~50 token English style descriptor
    }
    """

def extraer_anclas_personaje(ruta_personaje: str, nombre_personaje: str) -> dict:
    """
    Returns:
    {
        "name": str,
        "anchors_block": str    # e.g., "young man with disheveled dark curly hair, navy blue work coat, amber scarf"
    }
    """
```

### `pasos/p6_assets.py` ↔ `motores/imagen_openai/yieldchat_imagen.py`
```python
def generar_imagen_yieldchat(
    prompt: str,
    referencias: list = None,
    tamano: str = "1024x576",
    negative_prompt: str = "",
    adn_estilo: dict = None
) -> tuple[bytes | None, str | None, dict | None]:
    """
    Generates image using resilient provider cascade (Agnes AI primary with b64_json).
    Returns:
    (png_bytes, error_message, metadata_dict)
    metadata_dict includes: {"proveedor": "agnes", "formato": "b64_json", "latencia_s": float, "es_lienzo_emergencia": bool}
    """
```

### `motores/calidad_visual.py` (QA Judge Interface)
```python
def auditar_imagen_generada(
    ruta_o_bytes_imagen: str | bytes,
    ruta_referencia_estilo: str = None,
    encuadre_esperado: str = None
) -> dict:
    """
    Returns:
    {
        "es_valida": bool,
        "es_lienzo_emergencia": bool,
        "distancia_histograma_bhattacharyya": float, # 0.0 (identical) to 1.0 (disjoint)
        "cumple_estilo": bool,                      # distance < 0.65 threshold
        "cumple_encuadre": bool,
        "detalles": list[str]
    }
    """
```

---

## Code Layout
- `pasos/inversion_visual.py` (New): Multimodal vision extraction (Gemini 2.5 Flash) and local DNA caching.
- `pasos/p6_assets.py` (Modify): Modular prompt builder, remove 14 KB Spanish meta-rules and phantom references.
- `motores/imagen_openai/yieldchat_imagen.py` (Modify): Engine adapter, force b64_json in Agnes AI, remove 280-char truncation, cache protection.
- `motores/calidad_visual.py` (New): Adversarial visual QA judge using OpenCV and NumPy.
- `tests/test_e2e_visual_pipeline.py` (New): Opaque-box E2E test suite (Tiers 1-4).
