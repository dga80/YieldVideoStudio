"""Pipeline de generación de imágenes de YieldChat con fallback resiliente.

Genera ilustraciones y planos con estética de YouTube Faceless (16:9 y 9:16).
Si no hay clave activa de imágenes o el proveedor externo tiene restricciones,
genera un lienzo cinematográfico de alta resolución con las directrices visuales
para que el pipeline de vídeo, audio y subtítulos nunca se detenga.
"""
import base64
import hashlib
import io
import math
import os
import random
import re
import ssl
import time
import urllib.parse
import urllib.request
import json
import threading
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RATIO_MAP = {
    "apaisado": (1280, 720),
    "16:9": (1280, 720),
    "vertical": (720, 1280),
    "9:16": (720, 1280),
    "cuadrado": (1024, 1024),
    "1:1": (1024, 1024)
}


def extraer_guia_estilo(raw_prompt):
    """Extrae el bloque de la guía de estilo si está presente en el prompt."""
    m = re.search(r"Style guide, follow it to the letter:\s*(.*?)(?=\s*(?:Reference image|Todo prompt|HOW CHARACTERS|\Z))", raw_prompt, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _limpiar_negativos_para_deteccion(texto):
    """Elimina cláusulas negativas o de exclusión para evitar falsos positivos."""
    if not texto:
        return ""
    t = re.sub(
        r"(?:never\s+do\s+this[^\.\n]*|prohibid[oa][^\.\n]*|absolutely\s+no[^\.\n]*|zero\s+(?:2d|outlines?|drawing|strokes?|lines?|vector)[^\.\n]*|evitar\s*:[^\.\n]*|negative\s+prompt\s*:[^\.\n]*)",
        " ", texto, flags=re.IGNORECASE
    )
    t = re.sub(
        r"\b(?:no|sin|without)\s+(?:cartoon|anime|cel[- ]shading|stick[- ]figures?|stickman|monigotes?|2d|vector|drawing\s+lines?|outlines?|3d\s+render)\b[^\.,;\n]*",
        " ", t, flags=re.IGNORECASE
    )
    return t


def detectar_tipo_estilo(raw_prompt, referencias=None):
    """Determina si el estilo es realista/fotográfico, 3D, monigotes/stick, o 2D/ilustración.
    
    Analiza las referencias aportadas, los metadatos del proyecto y la guía de estilo
    para asegurar la coherencia estética en planos con o sin personajes.
    """
    # 1. Analizar referencias pasadas
    if referencias:
        for r in referencias:
            ruta = r.get("ruta") if isinstance(r, dict) else str(r)
            if ruta:
                ruta_l = ruta.lower()
                if any(k in ruta_l for k in ("realista", "pr1a136e4961c", "fotografia", "fotorrealista")):
                    return "realista"
                if any(k in ruta_l for k in ("pr1a11c45bec0", "pr1a0f91a4e44", "cartoon", "stick", "monigote")):
                    return "stick"
                m_proy = re.search(r"proyectos/([^/]+)", ruta)
                if m_proy:
                    pid = m_proy.group(1)
                    for base_proy in [
                        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "proyectos", pid),
                        f"/Volumes/LaCie/asVideoStudio/proyectos/{pid}"
                    ]:
                        pjson = os.path.join(base_proy, "proyecto.json")
                        if os.path.isfile(pjson):
                            try:
                                import json
                                cfg = json.load(open(pjson))
                                est_l = str(cfg.get("estilo_light") or "").lower()
                                if any(k in est_l for k in ("realista", "fotografia", "pr1a136e4961c")):
                                    return "realista"
                                if any(k in est_l for k in ("pr1a11c45bec0", "pr1a0f91a4e44", "cartoon", "stick")):
                                    return "stick"
                            except Exception:
                                pass

    guia = extraer_guia_estilo(raw_prompt)
    analizar_raw = f"{raw_prompt} {guia}"
    analizar = _limpiar_negativos_para_deteccion(analizar_raw)

    # 1. Realista / Fotográfico / 35mm cinematográfico / Documental real
    if re.search(r"\b(photorealistic|fotorrealista|35mm|cinematography|hyperrealistic|hiperrealista|documentary cinematography|real life photography|raw photo|realistic skin textures|cinematic lighting)\b", analizar, re.I) and not re.search(r"\b(3d\s+render|cgi|polished\s+chrome|sci-fi\s+robot|pbr\s+shading)\b", analizar, re.I):
        return "realista"

    # 2. Monigotes / Stick figure / Cartoon Stick / Personajes esféricos estilizados
    if re.search(r"\b(stick[- ]figures?|stickfigure|monigote|stick\s*man|cartoon[-_ ]stick|cartoon\s*8[-_]10[-_]26|round\s+heads?|oval\s+heads?|cylindrical\s+limbs|cylindrical\s+bodies|heads\s+tall|without\s+visible\s+hair|noses\s+and\s+ears\s+are\s+completely\s+absent|no\s+visible\s+noses?\s+or\s+ears|mustard[- ]yellow|ocher\s+mustard)\b", analizar, re.I):
        return "stick"

    # 3. 3D / CGI / Robots Sci-Fi / PBR
    if re.search(r"\b(3d\s+environment|3d\s+render|cgi|polished\s+chrome|sci-fi\s+robot|pbr\s+shading|complex\s+reflections|realistic\s+3d)\b", analizar, re.I):
        return "3d"

    # 4. 2D / Ilustración / Anime / Vector / Comic
    if re.search(r"\b(2d\s+vector|anime|manga|comic|cartoon|flat\s+vector|line\s*art|drawing|illustration|sketch|whiteboard|vector-like|outline|cel\s+shading)\b", analizar, re.I):
        return "2d"

    return "general"


def guardar_en_cache_seguro(png_bytes: bytes, ruta_destino: str, meta: dict = None) -> bool:
    """Bloquea lienzos de emergencia o imágenes corruptas para evitar contaminar banco/imagenes."""
    if not png_bytes or len(png_bytes) < 2048:
        return False
    if meta and meta.get("es_lienzo_emergencia"):
        return False

    try:
        im = Image.open(io.BytesIO(png_bytes))
        w, h = im.size
        # Validar tamaño y firma de borde dorado (212, 175, 55)
        arr = np.array(im.convert("RGBA"))
        if w > 48 and h > 48:
            border_px = arr[24, 24:w-24, :3]
            gold = np.array([212, 175, 55])
            diffs = np.linalg.norm(border_px - gold, axis=1)
            if np.mean(diffs < 60) > 0.3:
                return False

        # Validar varianza cromática (lienzo ciego)
        arr_gray = np.array(im.convert("L"))
        if float(np.var(arr_gray)) < 5.0:
            return False

        os.makedirs(os.path.dirname(os.path.abspath(ruta_destino)), exist_ok=True)
        with open(ruta_destino, "wb") as fh:
            fh.write(png_bytes)
        return True
    except Exception:
        return False


def limpiar_y_condensar_prompt(raw_prompt, referencias=None):
    """Limpia el prompt eliminando directivas conversacionales sin truncar a 280 caracteres."""
    texto = raw_prompt.strip()

    # Si ya es un prompt modular o directo, preservarlo limpiando espacios
    # 1. Si hay corrección explícita, tiene prioridad
    m_corr = re.search(r"Correction,\s*this takes priority:\s*([^\.\n]+)", texto, re.I)
    correccion = m_corr.group(1).strip() if m_corr else ""

    # 2. Si hay escena concreta de plano
    m_scene = re.search(r"(?:^|\n|\.\s+)(?:Scene|Escena|SHOT|PLANO):\s*(.*?)(?=\.\s+(?:This shot|SHOT TYPE|Time of day|LETTERING|Correction)|$)", texto, re.DOTALL | re.IGNORECASE)
    if m_scene:
        res = m_scene.group(1).strip().replace("\n", " ")
        patterns_boilerplate = [
            r'not a physical location:?\s*',
            r'a clean conceptual composition on (?:a flat graphic|a graphic|an empty)?\s*backdrop,?\s*',
            r'in the exact same (?:flat vector )?style as the rest of the video,?\s*',
            r'with (?:the group|the character|small figures|\w+)[^,\.]*drawn (?:as the same stick-figure characters|matching the visual style)[^,\.]*,?\s*',
            r'integrated into the composition,?\s*',
            r'with small (?:stick )?figures integrated as part of the diagram[^,\.]*,?\s*',
            r'\(TONO:[^\)]+\)\s*',
        ]
        for pat in patterns_boilerplate:
            res = re.sub(pat, '', res, flags=re.IGNORECASE)
        res = re.sub(r'^\s*[,.\s]+', '', res)
        res = re.sub(r'\s+', ' ', res).strip()

        # Reemplazar tokens de personajes para evitar que el modelo asuma personas humanas reales
        tipo = detectar_tipo_estilo(raw_prompt, referencias)
        if tipo == "stick":
            # Extraer y sustituir personaje en "with the character '...' "
            m_char = re.search(r"with the character [\'\"]?([a-zA-Z0-9_]+)[\'\"]?", raw_prompt, re.I)
            char_name = m_char.group(1) if m_char else None

            res = re.sub(r"with the character [\'\"]?[a-zA-Z0-9_]+[\'\"]?,?\s*", "with the stylized comic stickman character, ", res, flags=re.I)
            if char_name and char_name.lower() not in ("the", "a", "an", "asset", "scene"):
                res = re.sub(rf"\b{re.escape(char_name)}\b", "the stylized stickman character", res, flags=re.I)

            tokens_reparto = [
                'protagonista', 'superviviente', 'survivor', 'protagonist', 'pareja',
                'acusado', 'juez', 'analistas_financieros', 'ceos_wallstreet',
                'lideres_viejo_mundo', 'nuevos_lideres', 'presidente_a', 'presidente_b'
            ]
            for token in tokens_reparto:
                res = re.sub(rf"\b{token}\'s\s+face\b", "the stylized stickman character", res, flags=re.I)
                res = re.sub(rf"\b{token}\'s\b", "the stylized stickman's", res, flags=re.I)
                res = re.sub(rf"[\'\"\b]{token}s?[\'\"\b]?", "the stylized stickman character", res, flags=re.IGNORECASE)
            res = re.sub(r"'(asset:\w+|\w+)'", r"the stylized stickman character '\1'", res)

            # Eliminar descripciones anatómicas o fotográficas que confunden a la IA
            res = re.sub(r'\brepresenting people\b', 'representing small stick figures', res, flags=re.I)
            res = re.sub(r'\bhuman\s+shoulder\b', 'stylized stick figure shoulder', res, flags=re.I)
            res = re.sub(r'\b(?:a\s+)?(?:tight\s+)?close-up\s+portrait\s+of\s+(?:the\s+)?(?:survivor|character|protagonist|the stylized stickman character)?(?:\'s\s+face)?', 'a medium shot of the stylized stickman character', res, flags=re.I)
            res = re.sub(r'\bportrait\s+of\b', 'drawing of the stylized stickman character', res, flags=re.I)
            res = re.sub(r"\b(?:The\s+)?(?:survivor|character|protagonist|the stylized stickman character)\'s\s+(?:distorted\s+)?face\b", "the stylized stickman character", res, flags=re.I)
            res = re.sub(r'\btheir face etched with worry\b', 'looking stressed', res, flags=re.I)
            res = re.sub(r'\breflected faintly on a [^\.]*screen\b', 'near the computer monitor', res, flags=re.I)
            res = re.sub(r'\b(?:A\s+)?(?:tight\s+)?close-up\s+[^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'\bA close-up of the [^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'\b\w+\s+faces:[^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'\bNo smiling\.\s*', '', res, flags=re.I)
            res = re.sub(r'\b(?:Their|His|Her|The)\s+eyes\s+[^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'\b(?:Their|His|Her|The)\s+mouth\s+[^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'\bmouth slightly agape\b', '', res, flags=re.I)
            res = re.sub(r'\bFrom over the (?:the )?stylized stickman\'s shoulder,\s*', 'From behind the stylized stickman character, ', res, flags=re.I)
            res = re.sub(r'\bFrom ground level, the [^\.]*feet are visible[^\.]*\.', 'The stylized stickman character is walking.', res, flags=re.I)
            res = re.sub(r'\b(photo|portrait|face|picture)\s+(?:on|in)\s+(?:screen|door|window|frame|monitor|wall)\b', 'empty background', res, flags=re.I)
            res = re.sub(r'\b(framed photos?|picture frames?|photo frames?|portraits?|passport photos?|polaroids?)\b', '', res, flags=re.I)
            res = re.sub(r'\bThis shot accompanies the narration line:[^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'\bShow the specific moment[^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'\bNever a generic view[^\.]*\.', '', res, flags=re.I)
            res = re.sub(r'^\s*[,.\s]+', '', res)
            res = re.sub(r'\s+', ' ', res).strip()
        escena = res
    else:
        escena = ""

    # 3. Detectar si hay prompt de eje o sujeto principal
    m_sujeto = re.search(r"\b(A single character[^\.\n]+|Three ordinary people[^\.\n]+|A wide shot[^\.\n]+|A wide exterior[^\.\n]+|A close-up of[^\.\n]+|A simple schematic[^\.\n]+)", texto, re.I)
    sujeto = m_sujeto.group(1).strip() if m_sujeto else ""

    partes = []
    if correccion:
        partes.append(correccion)
    if escena:
        partes.append(escena)
    if sujeto and sujeto not in escena:
        partes.append(sujeto)

    if not partes:
        lineas = []
        for l in texto.splitlines():
            l_limpia = l.strip()
            if not l_limpia:
                continue
            if any(l_limpia.startswith(pref) for pref in (
                "Produce one single", "Draw one single", "Reference image", "Your output is ONE",
                "The written style guide", "No watermarks", "The language of"
            )):
                continue
            lineas.append(l_limpia)
        if lineas:
            partes.append(". ".join(lineas))
        else:
            partes.append(texto)

    prompt_resumen = ", ".join(partes)
    return prompt_resumen.strip()


def enriquecer_prompt(raw_prompt, tamano="apaisado", referencias=None):
    """Enriquece el prompt respetando su contenido y asegurando las anclas de estilo visual requeridas."""
    limpio = limpiar_y_condensar_prompt(raw_prompt, referencias)

    # Si ya viene con estilo completo, no duplicar
    if "dramatic 2d comic" in limpio.lower() or "clean 2d vector" in limpio.lower():
        return limpio

    tipo = detectar_tipo_estilo(raw_prompt, referencias)
    partes = []

    if tipo == "stick":
        tiene_personaje = bool(re.search(
            r"(?:with the character|cast sheet for|draw those exact characters|faces?: mouth|sad faces|angry faces|happy faces|smiling faces|stickman|superviviente|protagonista)\b",
            raw_prompt, re.I
        ))
        if tiene_personaje:
            partes.append(
                "Dramatic 2D comic vector illustration, animated graphic novel art style. "
                "A stylized cartoon stickman character with bald round white sphere head, large expressive tired eyes with dark circles under eyes, small pupils, ocher mustard-yellow knit sweater and blue denim jeans. "
                "Cel shading with soft graphic shadows, crisp dark ink outlines, dark high-contrast atmospheric scene with volumetric rim light around silhouettes. "
                "Single consistent 2D cartoon drawing throughout the whole image. ONLY stylized stickman characters are present. "
                "Pure flat 2D graphic comic illustration."
            )
            partes.append(limpio)
        else:
            partes.append(
                "Dramatic 2D comic vector illustration, animated graphic novel art style. "
                "Clean dark ink outlines, flat cel shaded colors, dark atmospheric scenery with dramatic volumetric rim lighting, zero people. "
                "Scenic environmental background illustration only, completely devoid of people, no characters, no human figures, empty environment."
            )
            partes.append(limpio)
    elif tipo == "2d":
        tiene_personaje = bool(re.search(
            r"(?:character|personaje|protagonista|people|person|man|woman|crowd)\b",
            raw_prompt, re.I
        ))
        if tiene_personaje:
            partes.append("Clean 2D vector animation style, flat digital graphic novel art, crisp dark ink line art on all objects and characters, vibrant flat palette, cel shading. Pure flat 2D cartoon illustration.")
            partes.append(limpio)
        else:
            partes.append("Clean 2D vector animation style, flat digital graphic novel art, crisp dark ink line art on all objects and scenery, vibrant flat palette, cel shading. Scenic background illustration only, completely devoid of people, empty environment.")
            partes.append(limpio)
    elif tipo == "3d":
        partes.append("Photorealistic 3D environment, cinematic lighting, 8k resolution")
        partes.append(limpio)
    elif tipo == "realista":
        tiene_persona = bool(re.search(r"\b(?:person|people|man|woman|character|child|face|portrait|crowd|human|boy|girl)\b", limpio, re.I))
        if tiene_persona:
            partes.append(
                "Ultra-realistic 35mm documentary photograph, award-winning cinematography, "
                "Caucasian people with European facial features and natural skin tones, "
                "real human proportions, natural skin texture with subtle pores, lifelike eyes and authentic expression, "
                "dramatic volumetric natural lighting, shallow depth of field, high detail 8k. "
                "Completely realistic photography, zero 2D illustration, no drawing lines, no cartoon, no anime, no 3D render."
            )
        else:
            partes.append(
                "Ultra-realistic 35mm documentary photograph, award-winning cinematography, "
                "authentic natural lighting, physical textures and reflections, optical lens depth of field, high detail 8k. "
                "Completely realistic photography, zero 2D illustration, no drawing lines, no cartoon, no anime, no 3D render."
            )
        partes.append(limpio)
    else:
        partes.append(limpio)

    return ", ".join(partes)


def _resolver_referencia_real(referencias, prompt, width=1280, height=720):
    """Rescata una ilustracion de referencia autentica si el generador web falla o esta saturado."""
    import glob
    candidatas = []

    # 1. Mirar en referencias pasadas explicitas
    for r in (referencias or []):
        ruta = r.get("ruta") if isinstance(r, dict) else str(r)
        if ruta and os.path.isfile(ruta):
            candidatas.append(ruta)

    # 2. Si no hay directas, buscar en aportadas del estudio y banco de presets
    if not candidatas:
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        patrones = [
            os.path.join(raiz, "proyectos", "*", "estilo", "aportadas", "*"),
            "/Volumes/LaCie/asVideoStudio/proyectos/*/estilo/aportadas/*",
            os.path.join(raiz, "banco", "presets", "*", "*.png"),
            os.path.join(raiz, "proyectos", "*", "estilo", "dibujadas", "*"),
        ]
        for pat in patrones:
            for f in glob.glob(pat):
                b = os.path.basename(f).lower()
                if f.lower().endswith((".png", ".jpg", ".jpeg")) and not b.startswith("miniatura") and "muestra" not in b:
                    try:
                        if os.path.getsize(f) > 35000:  # descartar lienzos de emergencia de 10-13KB
                            candidatas.append(f)
                    except OSError:
                        pass

    if not candidatas:
        return None

    candidatas = sorted(list(set(candidatas)))
    h = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    elegida = candidatas[h % len(candidatas)]

    try:
        im = Image.open(elegida)
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        im.thumbnail((width, height), Image.Resampling.LANCZOS)
        fondo = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        offset = ((width - im.width) // 2, (height - im.height) // 2)
        fondo.paste(im, offset, im if im.mode == "RGBA" else None)
        buf = io.BytesIO()
        fondo.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _crear_lienzo_cinematografico(prompt, width, height):
    """Crea una tarjeta visual de alta definición armónica con el estilo pedido."""
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    tipo = detectar_tipo_estilo(prompt)
    es_2d = tipo in ("2d", "stick")

    if es_2d:
        # Fondo blanco limpio para estilos de animación 2D / monigotes
        draw.rectangle([(0, 0), (width, height)], fill=(253, 252, 253, 255))
        # Franja verde minimalista en la base
        draw.rectangle([(0, height - 80), (width, height)], fill=(120, 180, 120, 255))
        # Suelo negro
        draw.line([(0, height - 80), (width, height - 80)], fill=(20, 20, 20, 255), width=3)
    else:
        # Huella única del prompt para variar sutilmente el degradado
        h = hashlib.sha256(prompt.encode("utf-8")).digest()
        r_base = 16 + (h[0] % 30)
        g_base = 20 + (h[1] % 30)
        b_base = 28 + (h[2] % 40)
        delta_r = 12 + (h[3] % 18)
        delta_g = 14 + (h[4] % 18)
        delta_b = 20 + (h[5] % 22)

        for y in range(height):
            ratio = y / max(1, height)
            r = int(r_base + ratio * delta_r)
            g = int(g_base + ratio * delta_g)
            b = int(b_base + ratio * delta_b)
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

        draw.rectangle([(24, 24), (width - 24, height - 24)], outline=(212, 175, 55, 120), width=2)
        draw.rectangle([(32, 32), (width - 32, height - 32)], outline=(50, 60, 80, 80), width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_SEMAFORO_BANANA = None
_LOCK_INIT = threading.Lock()

def _get_semaforo():
    global _SEMAFORO_BANANA
    if _SEMAFORO_BANANA is None:
        with _LOCK_INIT:
            if _SEMAFORO_BANANA is None:
                _SEMAFORO_BANANA = threading.Semaphore(1)
    return _SEMAFORO_BANANA


def _obtener_clave_banana():
    clave = os.environ.get("POLLINATIONS_API_KEY") or os.environ.get("BANANA_API_KEY")
    if clave:
        return clave.strip()
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_file = os.path.join(raiz, "secretos", ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"^(?:POLLINATIONS_API_KEY|BANANA_API_KEY)=(.*)$", line.strip())
                    if m and m.group(1).strip():
                        return m.group(1).strip()
        except Exception:
            pass
    ruta = os.path.join(raiz, "secretos", "claves.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            for k in ("pollinations", "banana", "nano_banana"):
                c = d.get(k)
                if isinstance(c, dict) and c.get("clave"):
                    return str(c["clave"]).strip()
                elif isinstance(c, str) and c.strip():
                    return c.strip()
        except Exception:
            pass
    return ""


def _obtener_clave_siliconflow():
    clave = os.environ.get("SILICONFLOW_API_KEY")
    if clave:
        return clave.strip()
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_file = os.path.join(raiz, "secretos", ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"^SILICONFLOW_API_KEY=(.*)$", line.strip())
                    if m and m.group(1).strip():
                        return m.group(1).strip()
        except Exception:
            pass
    ruta = os.path.join(raiz, "secretos", "claves.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            c = d.get("siliconflow")
            if isinstance(c, dict) and c.get("clave"):
                return str(c["clave"]).strip()
            elif isinstance(c, str) and c.strip():
                return c.strip()
        except Exception:
            pass
    return ""


def _obtener_clave_agnes():
    clave = os.environ.get("AGNES_API_KEY")
    if clave:
        return clave.strip()
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_file = os.path.join(raiz, "secretos", ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"^AGNES_API_KEY=(.*)$", line.strip())
                    if m and m.group(1).strip():
                        return m.group(1).strip()
        except Exception:
            pass
    ruta = os.path.join(raiz, "secretos", "claves.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            c = d.get("agnes")
            if isinstance(c, dict) and c.get("clave"):
                return str(c["clave"]).strip()
            elif isinstance(c, str) and c.strip():
                return c.strip()
        except Exception:
            pass
    return ""


def _obtener_generador_preferido():
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ruta = os.path.join(raiz, "ajustes.json")
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            gen = str(d.get("generador_imagen") or "").strip().lower()
            if gen in ("agnes", "siliconflow", "auto"):
                return gen
        except Exception:
            pass
    return "agnes"


_SEMAFORO_AGNES = threading.Semaphore(2)


def _intentar_generar_agnes(prompt, width, height, tamano="apaisado", referencias=None):
    """Genera la imagen con Agnes AI (OpenAI-compatible) usando agnes-image-2.1-flash con reintentos."""
    api_key = _obtener_clave_agnes()
    if not api_key:
        return None, None

    import requests
    url = "https://apihub.agnes-ai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    img_size = "1024x576" if tamano in ("apaisado", "16:9") else "1024x1024"
    prompt_completo = enriquecer_prompt(prompt, tamano, referencias=referencias)

    payload = {
        "model": "agnes-image-2.1-flash",
        "prompt": prompt_completo,
        "size": img_size,
        "response_format": "b64_json"
    }

    for intento in range(3):
        try:
            with _SEMAFORO_AGNES:
                resp = requests.post(url, json=payload, headers=headers, timeout=45)
            if resp.status_code == 200:
                data = resp.json()
                data_arr = data.get("data") or data.get("images") or []
                if data_arr:
                    b64 = data_arr[0].get("b64_json")
                    img_url = data_arr[0].get("url")
                    if b64:
                        raw = base64.b64decode(b64)
                        im = Image.open(io.BytesIO(raw))
                        if im.size != (width, height):
                            im = im.resize((width, height), Image.Resampling.LANCZOS)
                        if im.mode != "RGBA":
                            im = im.convert("RGBA")
                        out = io.BytesIO()
                        im.save(out, format="PNG")
                        return out.getvalue(), "Agnes Image 2.1 Flash (Agnes AI)"
                    elif img_url:
                        img_resp = requests.get(img_url, timeout=30)
                        if img_resp.status_code == 200:
                            im = Image.open(io.BytesIO(img_resp.content))
                            if im.size != (width, height):
                                im = im.resize((width, height), Image.Resampling.LANCZOS)
                            if im.mode != "RGBA":
                                im = im.convert("RGBA")
                            out = io.BytesIO()
                            im.save(out, format="PNG")
                            return out.getvalue(), "Agnes Image 2.1 Flash (Agnes AI)"
            elif resp.status_code in (429, 500, 502, 503, 504):
                pausa = 8.0 * (intento + 1)
                try:
                    print(f"[imagen_yieldchat] Agnes AI HTTP {resp.status_code} en intento {intento+1}, esperando {pausa:.0f}s...", flush=True)
                except Exception:
                    pass
                time.sleep(pausa)
                continue
            else:
                try:
                    print(f"[imagen_yieldchat] Agnes AI HTTP {resp.status_code}: {resp.text[:150]}", flush=True)
                except Exception:
                    pass
                time.sleep(3.0)
        except Exception as e:
            try:
                print(f"[imagen_yieldchat] Agnes AI intento {intento+1} error: {e}", flush=True)
            except Exception:
                pass
            time.sleep((intento + 1) * 3.0)

    return None, None


def _intentar_generar_siliconflow(prompt, width, height, tamano="apaisado", referencias=None):
    """Genera la imagen con SiliconFlow usando Tongyi-MAI/Z-Image-Turbo o FLUX."""
    api_key = _obtener_clave_siliconflow()
    if not api_key:
        return None, None

    import requests
    url = "https://api.siliconflow.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    img_size = "1024x576" if tamano in ("apaisado", "16:9") else "1024x1024"
    prompt_completo = enriquecer_prompt(prompt, tamano, referencias=referencias)

    modelos = [
        "black-forest-labs/FLUX.1-schnell",
        "Tongyi-MAI/Z-Image-Turbo"
    ]

    for mod in modelos:
        try:
            payload = {
                "model": mod,
                "prompt": prompt_completo,
                "image_size": img_size
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                img_url = (data.get("images") or [{}])[0].get("url") or (data.get("data") or [{}])[0].get("url")
                if img_url:
                    img_resp = requests.get(img_url, timeout=20)
                    if img_resp.status_code == 200:
                        im = Image.open(io.BytesIO(img_resp.content))
                        if im.size != (width, height):
                            im = im.resize((width, height), Image.Resampling.LANCZOS)
                        if im.mode != "RGBA":
                            im = im.convert("RGBA")
                        out = io.BytesIO()
                        im.save(out, format="PNG")
                        return out.getvalue(), f"{mod} (SiliconFlow)"
            elif resp.status_code in (401, 402):
                # Saldo insuficiente o clave invalida en SiliconFlow
                break
        except Exception:
            continue
    return None, None


def _intentar_generar_gemini(prompt, width, height, tamano="apaisado", referencias=None):
    """Intenta generar la imagen usando los modelos de imagen oficiales de Google Gemini."""
    try:
        from pasos import gemini_cliente
    except ImportError:
        try:
            import gemini_cliente
        except ImportError:
            return None, None

    api_key = gemini_cliente.obtener_api_key()
    if not api_key:
        return None, None

    modelos = [
        "gemini-2.5-flash-image",
        "gemini-3.1-flash-image",
        "gemini-3-pro-image",
        "gemini-3.1-flash-lite-image"
    ]

    prompt_limpio = enriquecer_prompt(prompt, tamano, referencias=referencias)
    payload = {
        "contents": [{"parts": [{"text": prompt_limpio}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"]
        }
    }

    import requests
    import base64

    for modelo in modelos:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    for p in parts:
                        if "inlineData" in p and p["inlineData"].get("data"):
                            raw = base64.b64decode(p["inlineData"]["data"])
                            img = Image.open(io.BytesIO(raw))
                            if img.size != (width, height):
                                img = img.resize((width, height), Image.Resampling.LANCZOS)
                            if img.mode != "RGBA":
                                img = img.convert("RGBA")
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            return buf.getvalue(), f"{modelo} (Google Gemini)"
            elif resp.status_code == 429:
                # Cuota no disponible / límite 0 en Free Tier de Google AI Studio
                continue
        except Exception:
            continue

    return None, None


def generar_imagen_yieldchat(prompt, referencias=None, tamano="apaisado", seed=None):
    """Genera la imagen en PNG usando el generador seleccionado (Agnes AI, SiliconFlow) o fallback resiliente."""
    t0 = time.time()
    width, height = RATIO_MAP.get(tamano, (1280, 720))

    preferido = _obtener_generador_preferido()

    # Si se seleccionó Agnes AI específicamente
    if preferido == "agnes":
        ag_bytes, ag_modelo = _intentar_generar_agnes(prompt, width, height, tamano, referencias=referencias)
        if ag_bytes:
            segundos = time.time() - t0
            return ag_bytes, {
                "segundos": round(segundos, 1),
                "quality": "high",
                "refs": len(referencias or []),
                "coste": 0.0,
                "modelo": ag_modelo,
                "tamano": f"{width}x{height}",
                "usage": {}
            }
        # Fallback a SiliconFlow si Agnes falló
        sf_bytes, sf_modelo = _intentar_generar_siliconflow(prompt, width, height, tamano, referencias=referencias)
        if sf_bytes:
            segundos = time.time() - t0
            return sf_bytes, {
                "segundos": round(segundos, 1),
                "quality": "high",
                "refs": len(referencias or []),
                "coste": 0.0,
                "modelo": sf_modelo,
                "tamano": f"{width}x{height}",
                "usage": {}
            }
    elif preferido == "siliconflow":
        # SiliconFlow prioritario
        sf_bytes, sf_modelo = _intentar_generar_siliconflow(prompt, width, height, tamano, referencias=referencias)
        if sf_bytes:
            segundos = time.time() - t0
            return sf_bytes, {
                "segundos": round(segundos, 1),
                "quality": "high",
                "refs": len(referencias or []),
                "coste": 0.0,
                "modelo": sf_modelo,
                "tamano": f"{width}x{height}",
                "usage": {}
            }
        # Fallback a Agnes si SiliconFlow falló o no tiene saldo
        ag_bytes, ag_modelo = _intentar_generar_agnes(prompt, width, height, tamano, referencias=referencias)
        if ag_bytes:
            segundos = time.time() - t0
            return ag_bytes, {
                "segundos": round(segundos, 1),
                "quality": "high",
                "refs": len(referencias or []),
                "coste": 0.0,
                "modelo": ag_modelo,
                "tamano": f"{width}x{height}",
                "usage": {}
            }
    else: # auto
        # Probar primero Agnes (gratuito) y luego SiliconFlow
        ag_bytes, ag_modelo = _intentar_generar_agnes(prompt, width, height, tamano, referencias=referencias)
        if ag_bytes:
            segundos = time.time() - t0
            return ag_bytes, {
                "segundos": round(segundos, 1),
                "quality": "high",
                "refs": len(referencias or []),
                "coste": 0.0,
                "modelo": ag_modelo,
                "tamano": f"{width}x{height}",
                "usage": {}
            }
        sf_bytes, sf_modelo = _intentar_generar_siliconflow(prompt, width, height, tamano, referencias=referencias)
        if sf_bytes:
            segundos = time.time() - t0
            return sf_bytes, {
                "segundos": round(segundos, 1),
                "quality": "high",
                "refs": len(referencias or []),
                "coste": 0.0,
                "modelo": sf_modelo,
                "tamano": f"{width}x{height}",
                "usage": {}
            }

    # Si preferido no devolvió resultado, segundo intento con Agnes AI tras pausa
    time.sleep(5.0)
    ag_bytes, ag_modelo = _intentar_generar_agnes(prompt, width, height, tamano, referencias=referencias)
    if ag_bytes:
        segundos = time.time() - t0
        return ag_bytes, {
            "segundos": round(segundos, 1),
            "quality": "high",
            "refs": len(referencias or []),
            "coste": 0.0,
            "modelo": ag_modelo,
            "tamano": f"{width}x{height}",
            "usage": {}
        }

    raise RuntimeError("Agnes AI está temporalmente saturada (límite de peticiones por minuto). Espera 15 segundos y vuelve a pulsar.")

    segundos = time.time() - t0
    meta = {
        "segundos": round(segundos, 1),
        "quality": "high",
        "refs": len(referencias or []),
        "coste": 0.0,
        "modelo": modelo_nombre,
        "tamano": f"{width}x{height}",
        "usage": {}
    }
    return png_bytes, meta
