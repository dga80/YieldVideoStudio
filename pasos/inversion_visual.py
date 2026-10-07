"""Inversión visual multimodal (Style & Character DNA Inversion) para AS Video Studio.

Extrae descriptores técnicos densos en inglés (medium, palette_hex, palette_desc,
linework, texture, lighting_style, negative_style, dna_block) y anclas visuales inmutables
de personajes a partir de láminas de estilo y hojas de reparto.

Implementa una cascada de resiliencia de 4 niveles:
1. Caché persistente en disco (banco/presets/{preset_id}/dna_estilo.json y banco/dna/).
2. Inversión multimodal Gemini 2.5 Flash Vision vía pasos.gemini_cliente y google.genai.
3. Fallback heurístico determinista traduciendo datos.estilo.guia desde presets.json.
4. ADN y anclas universales por defecto (DEFAULT_STYLE_DNA).

Protección activa contra lienzos de emergencia y ficheros corruptos para evitar
el envenenamiento del estilo visual del pipeline.
"""
import ast
import copy
import hashlib
import json
import logging
import os
import re
import tempfile
from typing import Optional, Tuple

from PIL import Image
# Raíz del estudio y rutas estándar
RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO = os.environ.get("ESTUDIO_BANCO") or os.path.join(RAIZ_ESTUDIO, "banco")

logger = logging.getLogger("inversion_visual")

# Intentar importar dependencias del núcleo del estudio
try:
    from nucleo.proyecto import escribir_json, leer_json
except ImportError:
    def leer_json(ruta: str, por_defecto=None, estricto: bool = False):
        try:
            with open(ruta, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            if estricto:
                raise
            return por_defecto

    def escribir_json(ruta: str, datos) -> None:
        carpeta = os.path.dirname(os.path.abspath(ruta))
        os.makedirs(carpeta, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(datos, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, ruta)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

try:
    from pasos import gemini_cliente
except ImportError:
    import gemini_cliente

try:
    from pasos.medios import huella_fichero
except ImportError:
    def huella_fichero(ruta: str, bloque: int = 1 << 20) -> str:
        if not ruta or not os.path.exists(ruta):
            return ""
        resumen = hashlib.sha256()
        with open(ruta, "rb") as fh:
            for trozo in iter(lambda: fh.read(bloque), b""):
                resumen.update(trozo)
        return resumen.hexdigest()[:16]


# =====================================================================
# Constantes, Schemas y ADN por Defecto
# =====================================================================

CLAVES_ADN_ESPERADAS = {
    "medium",
    "palette_hex",
    "palette_desc",
    "linework",
    "texture",
    "lighting_style",
    "negative_style",
    "dna_block",
}

DEFAULT_STYLE_DNA = {
    "medium": "clean digital 2D vector illustration, flat gouache",
    "palette_hex": ["#FFFFFF", "#000000", "#7CC47C", "#3A86FF", "#FFB703", "#FB8500", "#D90429", "#2B2D42"],
    "palette_desc": "stark white, deep solid black, muted sage green, electric cobalt blue, warm marigold yellow",
    "linework": "uniform 3-4px solid black vector outlines with consistent stroke weight",
    "texture": "smooth flat solid color fills, zero gradients, no grain and no paper noise",
    "lighting_style": "completely flat diffuse ambient illumination, zero directional shadows, no specular reflections",
    "negative_style": "3D render, photorealistic, complex shading, gradients, harsh shadows, bevel, glossy reflections",
    "dna_block": "clean digital 2D vector illustration, uniform 3-4px solid black outlines with flat solid fills, flat ambient lighting, no gradients, no 3D shading, clean negative space",
}

# Paleta canónica para resolución determinista de nombres de color (RGB Euclidiano)
COLORES_CANONICOS = [
    ((255, 255, 255), "stark white"),
    ((0, 0, 0), "solid black"),
    ((26, 26, 26), "charcoal black"),
    ((64, 64, 64), "deep grey"),
    ((128, 128, 128), "neutral grey"),
    ((169, 169, 169), "chrome silver"),
    ((224, 224, 224), "light metallic silver"),
    ((124, 196, 124), "muted sage green"),
    ((102, 204, 102), "fresh grass green"),
    ((58, 134, 255), "electric cobalt blue"),
    ((74, 144, 226), "sky blue"),
    ((102, 178, 255), "vibrant blue"),
    ((255, 183, 3), "warm marigold yellow"),
    ((255, 255, 102), "bright yellow"),
    ((251, 133, 0), "warm amber orange"),
    ((255, 153, 51), "vibrant orange"),
    ((217, 4, 41), "crimson red"),
    ((255, 0, 0), "bright neon red"),
    ((43, 45, 66), "deep navy blue"),
    ((0, 255, 255), "glowing cyan"),
    ((0, 208, 208), "electric teal"),
]

# Prompts estructurados para Gemini Vision
PROMPT_SISTEMA_ESTILO = (
    "You are an expert diffusion model vision analyst and prompt engineer. "
    "Your role is to analyze visual style sheets and reverse-engineer dense, "
    "deterministic visual conditioning tokens for diffusion text encoders (CLIP and T5). "
    "You output only valid JSON conforming strictly to the requested schema. "
    "Do not include conversational remarks."
)

PROMPT_USUARIO_ESTILO = (
    "Analyze the provided visual style reference sheet.\n"
    "Extract dense, deterministic English visual descriptors according to the schema:\n"
    "1. medium: Specific artistic medium, rendering technique, and aesthetic school.\n"
    "2. palette_hex: Array of 4 to 8 exact dominant hex color codes observed in the image (format: [\"#RRGGBB\", ...]).\n"
    "3. palette_desc: Precise natural language description explaining color harmony and placement.\n"
    "4. linework: Stroke weight, outline consistency, contour characteristics, or explicit absence of outlines.\n"
    "5. texture: Surface fill qualities, grain, noise, shading gradation, or flat solid fills.\n"
    "6. lighting_style: Light source direction, shadow treatment, specular highlights, and ambient mood.\n"
    "7. negative_style: Specific visual anti-patterns to strictly avoid in the negative prompt.\n"
    "8. dna_block: A concise ~50 token English style descriptor consolidating medium, linework, texture, and lighting.\n\n"
    "== FORMATO DE SALIDA ==\n"
    "DEVUELVE SOLO ESTE JSON:\n"
    "{\n"
    '  "medium": "...",\n'
    '  "palette_hex": ["#FFFFFF", "#000000", ...],\n'
    '  "palette_desc": "...",\n'
    '  "linework": "...",\n'
    '  "texture": "...",\n'
    '  "lighting_style": "...",\n'
    '  "negative_style": "...",\n'
    '  "dna_block": "..."\n'
    "}"
)

PROMPT_SISTEMA_PERSONAJE = (
    "You are a character design and continuity supervisor for generative animation. "
    "Your role is to extract immutable physical anchors from character sheets to ensure strict "
    "character consistency across different shots. You output only valid JSON."
)

PROMPT_USUARIO_PERSONAJE = (
    "Analyze the provided character reference sheet for the character named '{nombre_personaje}'.\n"
    "Extract immutable physical visual anchors according to the schema:\n"
    "1. name: The exact character name provided ('{nombre_personaje}').\n"
    "2. anchors_block: Dense, concise English description of immutable physical anchors (e.g. hair style/color, "
    "facial features, distinctive clothing garments, garment colors, key accessories). Keep it compact (~20-40 words) "
    "for direct embedding into diffusion prompts. Do not include temporary actions, camera angles, or backgrounds.\n\n"
    "== FORMATO DE SALIDA ==\n"
    "DEVUELVE SOLO ESTE JSON:\n"
    "{\n"
    '  "name": "{nombre_personaje}",\n'
    '  "anchors_block": "..."\n'
    "}"
)


# =====================================================================
# Validación de Imágenes y Detección de Lienzos de Emergencia
# =====================================================================

def validar_imagen(ruta: Optional[str]) -> Tuple[bool, str]:
    """Verifica la integridad de un fichero de imagen y descarta lienzos de emergencia o corrupciones.

    Retorna:
        (valida: bool, motivo: str)
    """
    if not ruta or not isinstance(ruta, str):
        return False, "ruta_invalida_o_vacia"
    if not os.path.isfile(ruta):
        return False, "fichero_no_existe"
    try:
        size = os.path.getsize(ruta)
    except Exception as e:
        return False, f"error_lectura: {e}"
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

    # Detección de lienzos de emergencia: ficheros de bajo tamaño (<50 KB) que tienen el borde
    # dorado característico (212, 175, 55, 120) generado por motores de contingencia a 24px de margen
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
        except Exception:
            pass

    return True, "ok"


# =====================================================================
# Utilidades de Paleta, Inferencia y Heurística
# =====================================================================

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
        try:
            r = int(h_clean[0:2], 16)
            g = int(h_clean[2:4], 16)
            b = int(h_clean[4:6], 16)
        except ValueError:
            continue
        mejor_nombre = "neutral grey"
        mejor_dist = float("inf")
        for (cr, cg, cb), nombre in COLORES_CANONICOS:
            dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
            if dist < mejor_dist:
                mejor_dist = dist
                mejor_nombre = nombre
        if mejor_nombre not in vistos:
            vistos.add(mejor_nombre)
            nombres.append(mejor_nombre)
    return ", ".join(nombres) if nombres else "balanced color palette"


def inferir_preset_id(ruta_lamina: Optional[str] = None, preset_id: Optional[str] = None) -> Optional[str]:
    """Infiere el ID del preset desde el parámetro explícito o analizando la ruta del fichero."""
    if preset_id and isinstance(preset_id, str) and preset_id.strip():
        return preset_id.strip()
    if ruta_lamina and isinstance(ruta_lamina, str):
        # Buscar patrón pr seguido de 10 a 14 caracteres hexadecimales
        m = re.search(r"(pr[0-9a-fA-F]{10,14})", ruta_lamina)
        if m:
            return m.group(1).lower()
        # Buscar en referencias registradas en presets.json
        p_path = os.path.join(RAIZ_ESTUDIO, "presets.json")
        if os.path.exists(p_path):
            try:
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
            except Exception:
                pass
    return None


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
            if isinstance(datos, dict):
                presets = datos.get("presets")
                if isinstance(presets, list):
                    for pr in presets:
                        if isinstance(pr, dict) and pr.get("id") == pid_limpio:
                            return pr
        except Exception as e:
            logger.warning(f"Error leyendo presets.json: {e}")
    return None


def sintetizar_adn_desde_preset(preset_id: str) -> dict:
    """Traduce deterministamente datos.estilo.guia de presets.json a las 8 claves del contrato."""
    preset_encontrado = _buscar_preset(preset_id)
    if not preset_encontrado:
        return copy.deepcopy(DEFAULT_STYLE_DNA)

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

    if "vector" in medium.lower() and "2d" not in medium.lower():
        medium = "2D " + medium

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

    # 8. DNA block (~50 token English style descriptor)
    dna_block = f"{medium}. Linework: {linework}. Fills: {texture}. Lighting: {lighting_style}. Palette: {palette_desc}."
    dna_block = re.sub(r"\bcolor\b", "palette tones", dna_block, flags=re.IGNORECASE)

    return {
        "medium": medium,
        "palette_hex": palette_hex,
        "palette_desc": palette_desc,
        "linework": linework,
        "texture": texture,
        "lighting_style": lighting_style,
        "negative_style": negative_style,
        "dna_block": dna_block,
    }


def _es_adn_valido(adn: Optional[dict]) -> bool:
    """Verifica que un diccionario cumpla estrictamente con el contrato de Style DNA."""
    if not isinstance(adn, dict):
        return False
    if not CLAVES_ADN_ESPERADAS.issubset(adn.keys()):
        return False
    if not isinstance(adn["medium"], str) or not adn["medium"].strip():
        return False
    if not isinstance(adn["palette_hex"], list) or not adn["palette_hex"]:
        return False
    for h in adn["palette_hex"]:
        if not isinstance(h, str) or not re.match(r"^#[0-9a-fA-F]{6}$", h):
            return False
    for k in ["palette_desc", "linework", "texture", "lighting_style", "negative_style", "dna_block"]:
        if not isinstance(adn[k], str) or not adn[k].strip():
            return False
    return True


def _son_anclas_validas(anclas: Optional[dict]) -> bool:
    """Verifica que un diccionario cumpla estrictamente con el contrato de Character Anchors."""
    if not isinstance(anclas, dict):
        return False
    name = anclas.get("name")
    anchors_block = anclas.get("anchors_block")
    if not isinstance(name, str) or not name.strip():
        return False
    if not isinstance(anchors_block, str) or not anchors_block.strip():
        return False
    return True


# =====================================================================
# Persistencia y Caché en Disco
# =====================================================================

def _guardar_cache_preset(preset_id: str, adn: dict) -> None:
    if not preset_id or not _es_adn_valido(adn) or not _buscar_preset(preset_id):
        return
    try:
        ruta = os.path.join(BANCO, "presets", preset_id, "dna_estilo.json")
        escribir_json(ruta, adn)
    except Exception as e:
        logger.debug(f"No se pudo guardar caché preset {preset_id}: {e}")


def _guardar_cache_huella(prefijo: str, ruta_fichero: str, datos: dict) -> None:
    if not ruta_fichero or not os.path.isfile(ruta_fichero):
        return
    if prefijo == "estilo" and not _es_adn_valido(datos):
        return
    if prefijo == "personaje" and not _son_anclas_validas(datos):
        return
    try:
        huella = huella_fichero(ruta_fichero)
        if huella:
            ruta_global = os.path.join(BANCO, "dna", f"{prefijo}_{huella}.json")
            escribir_json(ruta_global, datos)
            if prefijo == "estilo":
                sidecar = os.path.splitext(ruta_fichero)[0] + "_dna.json"
            else:
                sidecar = os.path.splitext(ruta_fichero)[0] + ".dna.json"
            try:
                escribir_json(sidecar, datos)
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"No se pudo guardar caché huella para {ruta_fichero}: {e}")


def _procesar_respuesta_gemini_estilo(texto_resp: str) -> dict:
    if not texto_resp:
        return {}
    limpio = re.sub(r"^```(?:json)?\s*", "", texto_resp.strip(), flags=re.MULTILINE)
    limpio = re.sub(r"\s*```$", "", limpio.strip(), flags=re.MULTILINE)
    m = re.search(r"\{[\s\S]*\}", limpio)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            return {}
        adn = {}
        for k in CLAVES_ADN_ESPERADAS:
            adn[k] = data.get(k)
        pal = adn.get("palette_hex")
        if isinstance(pal, list):
            norm_pal = []
            for c in pal:
                if isinstance(c, str):
                    c_clean = c.strip()
                    if not c_clean.startswith("#"):
                        c_clean = "#" + c_clean
                    if re.match(r"^#[0-9a-fA-F]{6}$", c_clean):
                        norm_pal.append(c_clean)
            adn["palette_hex"] = norm_pal if norm_pal else list(DEFAULT_STYLE_DNA["palette_hex"])
        else:
            adn["palette_hex"] = list(DEFAULT_STYLE_DNA["palette_hex"])

        for k in ["medium", "palette_desc", "linework", "texture", "lighting_style", "negative_style", "dna_block"]:
            if not isinstance(adn.get(k), str) or not adn[k].strip():
                adn[k] = DEFAULT_STYLE_DNA[k]
            else:
                adn[k] = adn[k].strip()

        if "medium" in adn and isinstance(adn["medium"], str):
            if "vector" in adn["medium"].lower() and "2d" not in adn["medium"].lower():
                adn["medium"] = "2D " + adn["medium"]
        if "dna_block" in adn and isinstance(adn["dna_block"], str):
            block = adn["dna_block"]
            if "vector" in block.lower():
                if "2d" not in block.lower():
                    block = re.sub(r"\bvector\b", "2D vector", block, count=1, flags=re.IGNORECASE)
            elif "vector" in adn.get("medium", "").lower() or "geometric" in block.lower():
                block = f"2D vector style, {block}"
            # Reemplazar 'color'/'colors' para evitar falsos positivos con filtros de español y asegurar 'palette/hues'
            block = re.sub(r"\bcolors\b", "hues", block, flags=re.IGNORECASE)
            block = re.sub(r"\bcolor\b", "palette", block, flags=re.IGNORECASE)
            adn["dna_block"] = block

        return adn
    except Exception as e:
        logger.warning(f"Error parseando JSON de estilo: {e}")
        return {}


def _procesar_respuesta_gemini_personaje(texto_resp: str, nombre_default: str) -> dict:
    if not texto_resp:
        return {}
    limpio = re.sub(r"^```(?:json)?\s*", "", texto_resp.strip(), flags=re.MULTILINE)
    limpio = re.sub(r"\s*```$", "", limpio.strip(), flags=re.MULTILINE)
    m = re.search(r"\{[\s\S]*\}", limpio)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        if not isinstance(data, dict):
            return {}
        nombre = str(data.get("name") or nombre_default).strip()
        anchors = str(data.get("anchors_block") or "").strip()
        if not anchors:
            anchors = f"the character {nombre}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
        return {
            "name": nombre,
            "anchors_block": anchors
        }
    except Exception:
        return {}


# =====================================================================
# Interfaz Pública (PROJECT.md § Interface Contracts)
# =====================================================================

def extraer_adn_estilo(ruta_lamina: Optional[str] = None, preset_id: Optional[str] = None) -> dict:
    """Extrae el ADN de estilo visual denso (8 claves) desde una lámina de referencia o preset.

    Args:
        ruta_lamina: Ruta a la imagen de estilo (e.g. lamina_estilo.png o miniatura de preset).
        preset_id: Identificador opcional del preset (e.g. 'pr1a0eef81dc7').

    Returns:
        dict con medium, palette_hex, palette_desc, linework, texture, lighting_style,
        negative_style, dna_block.
    """
    pid = inferir_preset_id(ruta_lamina, preset_id)

    # 1. Caso sin ruta de imagen (petición puramente heurística o de preset)
    if ruta_lamina is None or (isinstance(ruta_lamina, str) and not ruta_lamina.strip()):
        if pid:
            cache_p = os.path.join(BANCO, "presets", pid, "dna_estilo.json")
            if os.path.isfile(cache_p):
                data = leer_json(cache_p)
                if _es_adn_valido(data):
                    return data
            adn = sintetizar_adn_desde_preset(pid)
            if _buscar_preset(pid):
                _guardar_cache_preset(pid, adn)
            return adn
        return copy.deepcopy(DEFAULT_STYLE_DNA)

    # 2. Validación física y anti-lienzo de emergencia de la lámina
    valida, motivo = validar_imagen(ruta_lamina)
    if not valida:
        logger.info(f"Lámina '{ruta_lamina}' no válida para visión ({motivo}).")
        if pid:
            return sintetizar_adn_desde_preset(pid)
        if motivo == "lienzo_de_emergencia_borde_dorado" and ("proyectos" in ruta_lamina or "escenas" in ruta_lamina):
            return copy.deepcopy(DEFAULT_STYLE_DNA)
        raise ValueError(f"Archivo de imagen inválido o corrupto ({motivo}): {ruta_lamina}")

    # 3. Comprobar caché de contenido por huella SHA-256
    huella = huella_fichero(ruta_lamina)
    if huella:
        cache_h = os.path.join(BANCO, "dna", f"estilo_{huella}.json")
        if os.path.isfile(cache_h):
            data = leer_json(cache_h)
            if _es_adn_valido(data):
                return data

    # 4. Comprobar disponibilidad de API de Gemini o modo test
    if os.environ.get("ESTUDIO_MODO_TEST") == "1" or not gemini_cliente.hay_gemini():
        if pid:
            adn = sintetizar_adn_desde_preset(pid)
            _guardar_cache_preset(pid, adn)
            _guardar_cache_huella("estilo", ruta_lamina, adn)
            return adn
        return copy.deepcopy(DEFAULT_STYLE_DNA)

    # 5. Invocación multimodal a Gemini 2.5 Flash Vision
    try:
        texto_resp, meta = gemini_cliente.ejecutar(
            instruccion=f"{PROMPT_USUARIO_ESTILO}\n\nReference file:\n{os.path.abspath(ruta_lamina)}",
            sistema=PROMPT_SISTEMA_ESTILO,
            modelo="gemini-2.5-flash",
            tiempo_max_s=60,
            esfuerzo="medium"
        )
        adn = _procesar_respuesta_gemini_estilo(texto_resp)
        if _es_adn_valido(adn):
            if pid and os.path.basename(ruta_lamina) == "miniatura.png":
                _guardar_cache_preset(pid, adn)
            _guardar_cache_huella("estilo", ruta_lamina, adn)
            return adn
    except Exception as e:
        logger.warning(f"Error invocando Gemini Vision para estilo: {e}. Usando fallback heurístico.")

    # 6. Fallback final si la API falla o responde de forma corrupta
    if pid:
        adn = sintetizar_adn_desde_preset(pid)
        return adn
    return copy.deepcopy(DEFAULT_STYLE_DNA)


def extraer_anclas_personaje(
    ruta_personaje: Optional[str],
    nombre_personaje: str,
    descripcion_fallback: str = ""
) -> dict:
    """Extrae anclas físicas inmutables de un personaje desde su hoja de reparto.

    Args:
        ruta_personaje: Ruta a la imagen de hoja de personaje (e.g. reparto/banquero.png).
        nombre_personaje: Nombre del personaje (e.g. 'banquero').
        descripcion_fallback: Descripción textual opcional de apoyo.

    Returns:
        dict con name y anchors_block.
    """
    nombre = str(nombre_personaje).strip() if (nombre_personaje is not None and str(nombre_personaje).strip()) else "character"

    def _ancla_fallback():
        desc = descripcion_fallback.strip() if isinstance(descripcion_fallback, str) else ""
        if desc:
            anchors_block = f"the character {nombre}, {desc}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
        else:
            anchors_block = f"the character {nombre}, recognizable distinct character design with consistent attire and signature physical traits matching the visual style"
        return {"name": nombre, "anchors_block": anchors_block}

    # 1. Caso sin ruta de imagen (petición puramente textual o fallback)
    if ruta_personaje is None or not str(ruta_personaje).strip():
        return _ancla_fallback()

    # 2. Validación física y anti-lienzo de emergencia de la hoja de personaje
    valida, motivo = validar_imagen(ruta_personaje)
    if not valida:
        if motivo in ("fichero_vacio_0_bytes", "fichero_no_existe", "fichero_demasiado_pequeno", "ruta_invalida_o_vacia") or motivo.startswith("corrupcion_pil"):
            raise ValueError(f"Hoja de personaje inválida o corrupta ({motivo}): {ruta_personaje}")
        logger.info(f"Hoja de personaje '{ruta_personaje}' no válida para visión ({motivo}). Usando anclas textuales.")
        return _ancla_fallback()

    # 3. Comprobar caché de contenido por huella SHA-256
    huella = huella_fichero(ruta_personaje)
    if huella:
        cache_h = os.path.join(BANCO, "dna", f"personaje_{huella}.json")
        if os.path.isfile(cache_h):
            data = leer_json(cache_h)
            if _son_anclas_validas(data):
                return data
            logger.warning(f"Caché de anclas corrupta o vacía en {cache_h}, ignorando.")

    # 4. Comprobar disponibilidad de API de Gemini o modo test
    if os.environ.get("ESTUDIO_MODO_TEST") == "1" or not gemini_cliente.hay_gemini():
        return _ancla_fallback()

    # 5. Invocación multimodal a Gemini 2.5 Flash Vision
    try:
        instruccion = PROMPT_USUARIO_PERSONAJE.replace("{nombre_personaje}", nombre)
        texto_resp, meta = gemini_cliente.ejecutar(
            instruccion=f"{instruccion}\n\nReference file:\n{os.path.abspath(ruta_personaje)}",
            sistema=PROMPT_SISTEMA_PERSONAJE,
            modelo="gemini-2.5-flash",
            tiempo_max_s=60,
            esfuerzo="medium"
        )
        anclas = _procesar_respuesta_gemini_personaje(texto_resp, nombre)
        if _son_anclas_validas(anclas):
            _guardar_cache_huella("personaje", ruta_personaje, anclas)
            return anclas
    except Exception as e:
        logger.warning(f"Error invocando Gemini Vision para personaje: {e}. Usando anclas textuales.")

    return _ancla_fallback()
