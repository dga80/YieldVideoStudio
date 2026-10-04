"""Cliente oficial de Google Gemini para AS Video Studio (Yield Studio).

Sustituye la dependencia del CLI de Claude utilizando la API de Google Gemini
con la GEMINI_API_KEY configurada en secretos/.env, aplicando la lógica de
retención y fallback probada en YieldChat.
"""
import json
import os
import re
import sys
import time
import requests

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_SECRETOS = os.environ.get("ESTUDIO_SECRETOS") or os.path.join(RAIZ_ESTUDIO, "secretos")
FICHERO_ENV = os.path.join(CARPETA_SECRETOS, ".env")
FICHERO_CLAVES = os.path.join(CARPETA_SECRETOS, "claves.json")

# Modelos ordenados por estabilidad, disponibilidad y cuota activa comprobada
MODELOS_FLASH = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

MODELOS_PRO = [
    "gemini-3.1-pro-preview",
    "gemini-pro-latest",
]

SAFETY_SETTINGS_PERMISIVAS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"},
]

_API_KEY_CACHE = None


def obtener_api_key():
    global _API_KEY_CACHE
    if _API_KEY_CACHE:
        return _API_KEY_CACHE
    
    # 1. Variable de entorno directa
    clave = os.environ.get("GEMINI_API_KEY")
    if clave and clave.strip():
        _API_KEY_CACHE = clave.strip()
        return _API_KEY_CACHE

    # 2. Archivo secretos/.env
    if os.path.exists(FICHERO_ENV):
        try:
            with open(FICHERO_ENV, "r", encoding="utf-8-sig") as fh:
                for linea in fh:
                    m = re.match(r"^GEMINI_API_KEY=(.*)$", linea.strip())
                    if m and m.group(1).strip():
                        _API_KEY_CACHE = m.group(1).strip()
                        return _API_KEY_CACHE
        except Exception:
            pass

    # 3. Archivo secretos/claves.json
    if os.path.exists(FICHERO_CLAVES):
        try:
            with open(FICHERO_CLAVES, "r", encoding="utf-8-sig") as fh:
                datos = json.load(fh)
                if isinstance(datos, dict) and datos.get("gemini", {}).get("clave"):
                    _API_KEY_CACHE = datos["gemini"]["clave"].strip()
                    return _API_KEY_CACHE
        except Exception:
            pass

    return ""


def hay_gemini():
    return bool(obtener_api_key())


def _construir_partes(instruccion, cwd=None):
    """Construye las partes del payload, adjuntando imágenes como inline_data si se detectan."""
    partes = [{"text": instruccion}]
    patron = re.compile(r"[-*]?\s*([^\s\r\n\'\"]+\.(?:jpe?g|png|webp))", re.IGNORECASE)
    rutas_vistas = set()
    rutas_encontradas = []

    for linea in instruccion.splitlines():
        linea_limpia = linea.strip()
        if not linea_limpia:
            continue
        m = patron.search(linea_limpia)
        if m:
            posible = m.group(1).strip()
            candidatos = [posible]
            if cwd:
                candidatos.append(os.path.join(cwd, posible))
                candidatos.append(os.path.join(cwd, os.path.basename(posible)))
            for c in candidatos:
                if os.path.isfile(c):
                    real = os.path.abspath(c)
                    if real not in rutas_vistas:
                        rutas_vistas.add(real)
                        rutas_encontradas.append(real)
                    break

    if not rutas_encontradas:
        return partes

    import base64
    import io
    try:
        from PIL import Image
    except ImportError:
        Image = None

    for r in rutas_encontradas[:24]:
        try:
            with open(r, "rb") as fh:
                datos = fh.read()
            if Image is not None:
                try:
                    img = Image.open(io.BytesIO(datos))
                    if max(img.size) > 1024 or len(datos) > 400 * 1024:
                        img.thumbnail((1024, 1024))
                        buf = io.BytesIO()
                        img.convert("RGB").save(buf, format="JPEG", quality=80)
                        datos = buf.getvalue()
                except Exception:
                    pass
            mime = "image/jpeg" if not r.lower().endswith(".png") else "image/png"
            b64 = base64.b64encode(datos).decode("ascii")
            partes.append({"inline_data": {"mime_type": mime, "data": b64}})
        except Exception:
            continue

    return partes


def ejecutar(
    instruccion,
    modelo=None,
    esfuerzo="medium",
    sistema=None,
    cwd=None,
    tiempo_max_s=0,
    base_tiempo_s=180,
    avance=None,
    para="la tarea",
    **kwargs
):
    """Ejecuta una solicitud con Gemini manteniendo la firma (texto, sobre) esperada por el estudio."""
    api_key = obtener_api_key()
    if not api_key:
        raise RuntimeError("No se encontró GEMINI_API_KEY en secretos/.env")

    # Selección ordenada de candidatos de modelos
    candidatos = []
    if modelo:
        m_limpio = modelo.strip().lower()
        if m_limpio.startswith("gemini-pro") or "pro-preview" in m_limpio:
            candidatos.extend(MODELOS_PRO)
        elif "gemini" in m_limpio:
            candidatos.append(modelo.strip())

    for m in MODELOS_FLASH:
        if m not in candidatos:
            candidatos.append(m)

    timeout = int(tiempo_max_s or base_tiempo_s or 180)
    if timeout <= 0:
        timeout = 180

    t0 = time.time()
    # Si la instrucción trae el bloque CIERRE de Claude CLI ("ESCRIBE EL RESULTADO EN EL FICHERO salida.json..."),
    # como Gemini responde vía API y no con herramientas de shell, le indicamos devolver el JSON directamente.
    instruccion_limpia = re.sub(
        r'=+\s*COMO ENTREGARLO\s*=+\s*[\s\S]*?(?:Cuando este escrito,\s*responde solo con:\s*LISTO|$)',
        '\nDEVUELVE EL JSON COMPLETO Y VALIDO DIRECTAMENTE EN TU RESPUESTA:\n',
        instruccion,
        flags=re.IGNORECASE
    )
    partes_usuario = _construir_partes(instruccion_limpia, cwd=cwd)

    # Permitir hasta 2 vueltas completas sobre la lista de modelos ante picos de demanda
    for vuelta in range(2):
        for m_cand in candidatos:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_cand}:generateContent?key={api_key}"
            
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": partes_usuario
                    }
                ],
                "safetySettings": SAFETY_SETTINGS_PERMISIVAS,
                "generationConfig": {
                    "temperature": 0.7 if esfuerzo in ("high", "xhigh", "max") else 0.4,
                    "topP": 0.95,
                }
            }
            if sistema:
                payload["system_instruction"] = {
                    "parts": [{"text": sistema}]
                }

            # Hasta 2 intentos por modelo si hay congestión temporal (503/429)
            for reintento in range(2):
                try:
                    resp = requests.post(url, json=payload, timeout=timeout)
                    if resp.status_code == 200:
                        data = resp.json()
                        cands = data.get("candidates", [])
                        if not cands:
                            feedback = data.get("promptFeedback", {})
                            motivo = feedback.get("blockReason") or "sin candidatos"
                            ultimo_error = f"{m_cand}: respuesta sin candidatos (motivo: {motivo})"
                            break  # intentar con el siguiente modelo de la lista
                        
                        partes = cands[0].get("content", {}).get("parts", [])
                        if not partes:
                            motivo = cands[0].get("finishReason") or "sin partes"
                            ultimo_error = f"{m_cand}: candidato sin texto (finishReason: {motivo})"
                            break  # intentar con el siguiente modelo de la lista
                        
                        texto = "".join(p.get("text", "") for p in partes).strip()
                        if not texto:
                            ultimo_error = f"{m_cand}: texto de respuesta vacío"
                            break
                        
                        # Limpiar bloques markdown accidentales si la instrucción pedía JSON puro
                        if "== FORMATO DE SALIDA ==" in instruccion or "JSON" in instruccion or "DEVUELVE SOLO ESTE JSON" in instruccion:
                            m_json = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", texto)
                            if m_json:
                                posible_json = m_json.group(1).strip()
                                if posible_json.startswith("{") or posible_json.startswith("["):
                                    texto = posible_json

                        segundos = time.time() - t0
                        usage = data.get("usageMetadata", {})
                        in_tok = usage.get("promptTokenCount", 0)
                        out_tok = usage.get("candidatesTokenCount", 0)

                        sobre = {
                            "result": texto,
                            "usage": {
                                "input_tokens": in_tok,
                                "output_tokens": out_tok,
                                "total_tokens": usage.get("totalTokenCount", in_tok + out_tok)
                            },
                            "_ajuste": {
                                "modelo": m_cand,
                                "esfuerzo": esfuerzo,
                                "segundos": round(segundos, 2),
                                "tiempo_max_s": timeout,
                                "cuenta": "Google Gemini (YieldChat)"
                            },
                            "model": m_cand
                        }
                        if cwd and os.path.isdir(cwd) and "salida.json" in instruccion:
                            try:
                                with open(os.path.join(cwd, "salida.json"), "w", encoding="utf-8") as fh:
                                    fh.write(texto)
                            except Exception:
                                pass

                        return texto, sobre

                    elif resp.status_code == 429:
                        ultimo_error = f"HTTP 429: {resp.text[:200]}"
                        # Si la cuota de este modelo está totalmente agotada, pasar al siguiente sin reintentar
                        if "exceeded your current quota" in resp.text:
                            break
                        if reintento == 0:
                            time.sleep(1.5)
                            continue
                        break
                    elif resp.status_code == 503:
                        ultimo_error = f"HTTP 503: {resp.text[:200]}"
                        if reintento == 0:
                            time.sleep(1.5)
                            continue  # reintentar el mismo modelo tras breve pausa
                        break  # pasar al siguiente modelo
                    elif resp.status_code == 404:
                        # Modelo no existe o deprecado, pasar inmediatamente al siguiente
                        ultimo_error = f"HTTP 404: {resp.text[:150]}"
                        break
                    else:
                        ultimo_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                        break
                except requests.RequestException as e:
                    ultimo_error = f"Error de red con {m_cand}: {e}"
                    break

        if vuelta == 0:
            time.sleep(1.0)

    raise RuntimeError(f"Fallo al invocar Gemini para {para}: {ultimo_error}")
