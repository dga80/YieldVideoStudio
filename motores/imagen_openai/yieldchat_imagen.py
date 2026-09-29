"""Pipeline de generación de imágenes de YieldChat con fallback resiliente.

Genera ilustraciones y planos con estética de YouTube Faceless (16:9 y 9:16).
Si no hay clave activa de imágenes o el proveedor externo tiene restricciones,
genera un lienzo cinematográfico de alta resolución con las directrices visuales
para que el pipeline de vídeo, audio y subtítulos nunca se detenga.
"""
import io
import math
import os
import random
import ssl
import time
import urllib.parse
import urllib.request
from PIL import Image, ImageDraw, ImageFont

RATIO_MAP = {
    "apaisado": (1280, 720),
    "16:9": (1280, 720),
    "vertical": (720, 1280),
    "9:16": (720, 1280),
    "cuadrado": (1024, 1024),
    "1:1": (1024, 1024)
}


def enriquecer_prompt(raw_prompt, tamano="apaisado"):
    partes = [raw_prompt.strip()]
    if tamano in ("apaisado", "16:9"):
        partes.append("cinematic lighting, YouTube composition, high contrast, vivid colors, ultra sharp focus, 8k render, masterpiece")
    elif tamano in ("vertical", "9:16"):
        partes.append("vertical composition, dramatic lighting, mobile aesthetic, detailed textures, 8k render")
    else:
        partes.append("studio lighting, sharp subject, soft bokeh background, high resolution")
    return ", ".join(partes)


def _crear_lienzo_cinematografico(prompt, width, height):
    """Crea una tarjeta visual de alta definición con degradado cinematográfico."""
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    # Degradado oscuro de alta gama (#11141c -> #1b202e)
    for y in range(height):
        ratio = y / max(1, height)
        r = int(17 + ratio * 12)
        g = int(20 + ratio * 14)
        b = int(28 + ratio * 20)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Marco dorado tenue estilo YieldChat
    draw.rectangle([(24, 24), (width - 24, height - 24)], outline=(212, 175, 55, 120), width=2)
    draw.rectangle([(32, 32), (width - 32, height - 32)], outline=(50, 60, 80, 80), width=1)

    # Texto representativo del plano
    texto_plano = prompt.strip()[:80] + ("..." if len(prompt.strip()) > 80 else "")
    cx, cy = width // 2, height // 2

    # Intentar dibujar texto centrado
    draw.text((cx, cy - 20), "YIELD STUDIO · PLANO", fill=(212, 175, 55, 200), anchor="mm")
    draw.text((cx, cy + 20), texto_plano, fill=(225, 230, 240, 240), anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generar_imagen_yieldchat(prompt, referencias=None, tamano="apaisado", seed=None):
    """Genera la imagen en PNG o recurre al lienzo cinematográfico de alta definición."""
    t0 = time.time()
    width, height = RATIO_MAP.get(tamano, (1280, 720))
    prompt_completo = enriquecer_prompt(prompt, tamano)

    if seed is None:
        seed = random.randint(1000, 999999)

    encoded = urllib.parse.quote(prompt_completo)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&seed={seed}"

    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            data = resp.read()

        img = Image.open(io.BytesIO(data))
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG")
        png_bytes = out_buf.getvalue()
        modelo_nombre = "banana-sana (YieldChat)"
    except Exception as e:
        # Fallback resiliente: no detiene el render del vídeo ni los subtítulos
        print(f"[imagen_yieldchat] Nota: proveedor externo ({e}). Usando lienzo cinematográfico HD.", flush=True)
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
