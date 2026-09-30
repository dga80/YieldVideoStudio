"""Pipeline de generación de imágenes de YieldChat con fallback resiliente.

Genera ilustraciones y planos con estética de YouTube Faceless (16:9 y 9:16).
Si no hay clave activa de imágenes o el proveedor externo tiene restricciones,
genera un lienzo cinematográfico de alta resolución con las directrices visuales
para que el pipeline de vídeo, audio y subtítulos nunca se detenga.
"""
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
from PIL import Image, ImageDraw, ImageFont

RATIO_MAP = {
    "apaisado": (1280, 720),
    "16:9": (1280, 720),
    "vertical": (720, 1280),
    "9:16": (720, 1280),
    "cuadrado": (1024, 1024),
    "1:1": (1024, 1024)
}


def limpiar_y_condensar_prompt(raw_prompt):
    """Extrae el sujeto visual y el estilo esencial, descartando preámbulos extensos.

    Pollinations y APIs externas fallan con HTTP 402/414 si la URL excede 1000 caracteres.
    Condensar a < 280 caracteres garantiza respuestas rápidas, estables y fieles.
    """
    texto = raw_prompt.strip()

    # 1. Si hay corrección explícita, tiene prioridad
    m_corr = re.search(r"Correction,\s*this takes priority:\s*([^\.\n]+)", texto, re.I)
    correccion = m_corr.group(1).strip() if m_corr else ""

    # 2. Si hay escena concreta de plano
    m_scene = re.search(r"(?:^|\n|\.\s+)(?:Scene|Escena|SHOT|PLANO):\s*(.*?)(?=\.\s+(?:This shot|SHOT TYPE|Time of day|LETTERING|Correction)|$)", texto, re.DOTALL | re.IGNORECASE)
    if m_scene:
        res = m_scene.group(1).strip().replace("\n", " ")
        subparts = [p.strip() for p in res.split(".") if p.strip()]
        escena = ". ".join(subparts[:2])
    else:
        escena = ""

    # 3. Detectar si hay prompt de eje o sujeto principal
    m_sujeto = re.search(r"\b(A single character[^\.\n]+|Three ordinary people[^\.\n]+|A wide shot[^\.\n]+|A wide exterior[^\.\n]+|A close-up of[^\.\n]+|A simple schematic[^\.\n]+)", texto, re.I)
    sujeto = m_sujeto.group(1).strip() if m_sujeto else ""

    # 4. Extraer palabras clave de estilo
    m_estilo = re.search(r"\b(minimalist\s+2D[^\.\n]+|stick[- ]figure[^\.\n]+|flat\s+vector[^\.\n]+|anime[^\.\n]+|cartoon[^\.\n]+|comic\s+book[^\.\n]+|watercolor[^\.\n]+|line\s*art[^\.\n]+)", texto, re.I)
    estilo_clave = m_estilo.group(1).strip() if m_estilo else ""

    partes = []
    if correccion:
        partes.append(correccion)
    if escena:
        partes.append(escena)
    if sujeto and sujeto not in escena:
        partes.append(sujeto)
    if estilo_clave and estilo_clave not in escena and estilo_clave not in sujeto:
        partes.append(estilo_clave)

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
            partes.append(" ".join(lineas[:2]))
        else:
            partes.append(texto[:200])

    prompt_resumen = ", ".join(partes)
    if len(prompt_resumen) > 280:
        prompt_resumen = prompt_resumen[:277] + "..."
    return prompt_resumen


def enriquecer_prompt(raw_prompt, tamano="apaisado"):
    limpio = limpiar_y_condensar_prompt(raw_prompt)
    partes = [limpio]

    # Detectar si el estilo pide 2D / animación / ilustración plana
    es_2d = bool(re.search(
        r"\b(2d|flat|vector|minimalist|cartoon|anime|line\s*art|drawing|illustration|sketch|stick\s*figure|whiteboard|comic|dibujo)\b",
        raw_prompt, re.I
    ))

    if es_2d:
        partes.append("clean line art, 2D vector animation style, high quality illustration")
    else:
        if tamano in ("apaisado", "16:9"):
            partes.append("cinematic lighting, YouTube composition, sharp focus, high resolution")
        elif tamano in ("vertical", "9:16"):
            partes.append("vertical composition, dramatic lighting, detailed")
        else:
            partes.append("studio lighting, sharp subject, high resolution")

    return ", ".join(partes)


def _crear_lienzo_cinematografico(prompt, width, height):
    """Crea una tarjeta visual de alta definición con degradado cinematográfico único por plano."""
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    # Huella única del prompt para variar sutilmente el degradado y garantizar unicidad
    h = hashlib.sha256(prompt.encode("utf-8")).digest()
    r_base = 16 + (h[0] % 30)
    g_base = 20 + (h[1] % 30)
    b_base = 28 + (h[2] % 40)
    delta_r = 12 + (h[3] % 18)
    delta_g = 14 + (h[4] % 18)
    delta_b = 20 + (h[5] % 22)

    # Degradado oscuro de alta gama
    for y in range(height):
        ratio = y / max(1, height)
        r = int(r_base + ratio * delta_r)
        g = int(g_base + ratio * delta_g)
        b = int(b_base + ratio * delta_b)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Marco dorado tenue estilo YieldChat
    draw.rectangle([(24, 24), (width - 24, height - 24)], outline=(212, 175, 55, 120), width=2)
    draw.rectangle([(32, 32), (width - 32, height - 32)], outline=(50, 60, 80, 80), width=1)

    # Extraer la descripción visual real de la escena (saltando el preámbulo)
    m_scene = re.search(r"Scene:\s*(.*?)(?:\. This shot|\. SHOT TYPE|\. Time of day|$)", prompt, re.DOTALL | re.IGNORECASE)
    if m_scene and m_scene.group(1).strip():
        texto_plano = m_scene.group(1).strip()
    else:
        m_narr = re.search(r"narration line:\s*\"(.*?)\"", prompt, re.DOTALL | re.IGNORECASE)
        if m_narr and m_narr.group(1).strip():
            texto_plano = m_narr.group(1).strip()
        else:
            texto_plano = prompt.strip()[-100:]

    if len(texto_plano) > 100:
        texto_plano = texto_plano[:97] + "..."

    cx, cy = width // 2, height // 2

    # Intentar dibujar texto centrado con huella única
    tag_hex = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8].upper()
    draw.text((cx, cy - 20), f"YIELD STUDIO · PLANO {tag_hex}", fill=(212, 175, 55, 220), anchor="mm")
    draw.text((cx, cy + 20), texto_plano, fill=(225, 230, 240, 240), anchor="mm")

    # Identificador de huella único en esquina
    draw.text((width - 40, height - 35), f"REF {tag_hex}", fill=(180, 190, 210, 140), anchor="rm")

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
                _SEMAFORO_BANANA = threading.Semaphore(2)
    return _SEMAFORO_BANANA


def _obtener_clave_banana():
    clave = os.environ.get("POLLINATIONS_API_KEY") or os.environ.get("BANANA_API_KEY")
    if clave:
        return clave.strip()
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "secretos", "claves.json")
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


def _intentar_generar_gemini(prompt, width, height, tamano="apaisado"):
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

    prompt_limpio = enriquecer_prompt(prompt, tamano)
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
    """Genera la imagen en PNG usando Google Gemini o recurriendo a fallback resiliente."""
    t0 = time.time()
    width, height = RATIO_MAP.get(tamano, (1280, 720))

    # 1. Intentar primero con Google Gemini
    gemini_bytes, gemini_modelo = _intentar_generar_gemini(prompt, width, height, tamano)
    if gemini_bytes:
        segundos = time.time() - t0
        meta = {
            "segundos": round(segundos, 1),
            "quality": "high",
            "refs": len(referencias or []),
            "coste": 0.0,
            "modelo": gemini_modelo,
            "tamano": f"{width}x{height}",
            "usage": {}
        }
        return gemini_bytes, meta

    prompt_completo = enriquecer_prompt(prompt, tamano)

    if seed is None:
        seed = random.randint(1000, 999999)

    encoded = urllib.parse.quote(prompt_completo)
    api_key = _obtener_clave_banana()

    if api_key:
        url = f"https://gen.pollinations.ai/image/{encoded}?width={width}&height={height}&key={api_key}&seed={seed}"
    else:
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&seed={seed}"

    png_bytes = None
    modelo_nombre = "banana-sana (YieldChat)"
    ultimo_error = None

    sem = _get_semaforo()
    with sem:
        for intento in range(2):
            try:
                ctx = ssl._create_unverified_context()
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
                }
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
                    data = resp.read()

                img = Image.open(io.BytesIO(data))
                if img.mode != "RGBA":
                    img = img.convert("RGBA")

                out_buf = io.BytesIO()
                img.save(out_buf, format="PNG")
                png_bytes = out_buf.getvalue()
                break
            except Exception as e:
                ultimo_error = e
                time.sleep(1.5)

    if not png_bytes:
        # Fallback resiliente: no detiene el render del vídeo ni los subtítulos
        print(f"[imagen_yieldchat] Nota: proveedor externo ({ultimo_error}). Usando lienzo cinematográfico HD.", flush=True)
        png_bytes = _crear_lienzo_cinematografico(prompt, width, height)
        modelo_nombre = "yield-canvas (HD)"

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
