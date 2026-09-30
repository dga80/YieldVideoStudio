"""Motor de síntesis de voz con Microsoft Edge TTS y extracción de WordBoundary.

Genera locución con calidad neuronal en español e inglés sin coste ni límites de API,
devolviendo exactamente el formato WAV PCM s16le mono 44.1kHz y marcas por palabra
que requiere el motor de corte y subtítulos de AS Video Studio.
"""
import asyncio
import io
import os
import re
import subprocess
import edge_tts

SR = 44100

VOCES_EDGE = {
    "es": {
        "alvaro": "es-ES-AlvaroNeural",
        "elvira": "es-ES-ElviraNeural",
        "ximena": "es-ES-XimenaNeural",
        "jorge": "es-MX-JorgeNeural",
        "dalia": "es-MX-DaliaNeural",
        "gonzalo": "es-CO-GonzaloNeural",
        "tomas": "es-AR-TomasNeural",
    },
    "en": {
        "christopher": "en-US-ChristopherNeural",
        "guy": "en-US-GuyNeural",
        "jenny": "en-US-JennyNeural",
    },
    "fr": {
        "henri": "fr-FR-HenriNeural",
        "denise": "fr-FR-DeniseNeural",
    },
    "de": {
        "conrad": "de-DE-ConradNeural",
        "katja": "de-DE-KatjaNeural",
    },
    "it": {
        "diego": "it-IT-DiegoNeural",
        "elsa": "it-IT-ElsaNeural",
    },
    "pt": {
        "antonio": "pt-BR-AntonioNeural",
        "francisca": "pt-BR-FranciscaNeural",
    },
}

VOZ_DEFECTO = {
    "es": "es-ES-AlvaroNeural",
    "en": "en-US-ChristopherNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "pt": "pt-BR-AntonioNeural",
}


def resolver_voz(voz_solicitada, idioma="es"):
    idioma = str(idioma or "es").strip().lower()
    if not voz_solicitada:
        return VOZ_DEFECTO.get(idioma, VOZ_DEFECTO["es"])
    
    voz_str = str(voz_solicitada).strip()
    if "Neural" in voz_str:
        return voz_str
    
    cat = VOCES_EDGE.get(idioma, VOCES_EDGE.get("es", {}))
    for k, v in cat.items():
        if k in voz_str.lower():
            return v
    return VOZ_DEFECTO.get(idioma, VOZ_DEFECTO["es"])


def resolver_velocidad(velocidad):
    vel = str(velocidad or "normal").lower()
    if vel in ("fast", "rapida", "rápida"):
        return "+12%"
    elif vel in ("slow", "lenta"):
        return "-8%"
    elif vel in ("very_fast", "muy_rapida"):
        return "+20%"
    return "+0%"


async def _generar_stream(texto_limpio, voz, rate):
    comm = edge_tts.Communicate(texto_limpio, voice=voz, rate=rate, boundary="WordBoundary")
    mp3_buf = bytearray()
    palabras = []
    
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            mp3_buf.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            # 1 tick = 100ns (1e-7 s)
            ini = chunk["offset"] / 10_000_000.0
            dur = chunk["duration"] / 10_000_000.0
            palabras.append({
                "w": chunk["text"],
                "s": round(ini, 3),
                "e": round(ini + dur, 3)
            })
            
    return bytes(mp3_buf), palabras


def _convertir_a_wav(mp3_bytes):
    """Convierte el stream MP3 a WAV PCM mono 44.1kHz con FFmpeg."""
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", "pipe:0",
        "-ar", str(SR),
        "-ac", "1",
        "-f", "wav",
        "pipe:1"
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    wav_bytes, err = proc.communicate(input=mp3_bytes)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg error al convertir MP3 a WAV: {err.decode('utf-8', errors='ignore')}")
    return wav_bytes


def sintetizar_edge(texto, cfg=None, progreso=None):
    """Genera la toma continua en formato WAV y con word timestamps."""
    cfg = cfg or {}
    idioma = cfg.get("idioma", "es")
    voz = resolver_voz(cfg.get("voz_id"), idioma)
    rate = resolver_velocidad(cfg.get("velocidad"))

    # Limpiar posibles etiquetas SSML que Cartesia usaba (ej. <break time="..."/>)
    texto_limpio = re.sub(r"<[^>]+>", "", texto).strip()
    if not texto_limpio:
        raise ValueError("Texto de narración vacío")

    if progreso:
        progreso(0.1, f"sintetizando con {voz}")

    mp3_bytes, palabras = asyncio.run(_generar_stream(texto_limpio, voz, rate))
    if not mp3_bytes:
        raise RuntimeError("Edge-TTS no devolvió datos de audio")

    if progreso:
        progreso(0.7, "convirtiendo audio a WAV 44.1kHz")

    wav_bytes = _convertir_a_wav(mp3_bytes)

    # Duración precisa basada en el tamaño del audio PCM (sin cabecera 44 bytes)
    duracion = max(0.0, (len(wav_bytes) - 44) / (SR * 2))

    if progreso:
        progreso(1.0, f"toma completada ({len(palabras)} palabras)")

    return wav_bytes, duracion, palabras
