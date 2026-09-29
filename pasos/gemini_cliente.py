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

# Modelos en orden de preferencia (YieldChat candidates)
MODELOS_FLASH = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
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

    # Si se pasó un modelo específico de Claude o vacío, seleccionamos el de Gemini
    candidatos = list(MODELOS_FLASH)
    if modelo and "gemini" in modelo.lower():
        candidatos.insert(0, modelo.strip())

    timeout = int(tiempo_max_s or base_tiempo_s or 180)
    if timeout <= 0:
        timeout = 180

    t0 = time.time()
    ultimo_error = None

    for m_cand in candidatos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_cand}:generateContent?key={api_key}"
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": instruccion}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7 if esfuerzo in ("high", "xhigh", "max") else 0.4,
                "topP": 0.95,
            }
        }
        if sistema:
            payload["system_instruction"] = {
                "parts": [{"text": sistema}]
            }

        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates", [])
                if not cands:
                    raise RuntimeError("Gemini no devolvió candidatos en la respuesta")
                
                partes = cands[0].get("content", {}).get("parts", [])
                texto = "".join(p.get("text", "") for p in partes).strip()
                
                # Limpiar bloques markdown accidentales si la instrucción pedía JSON puro
                if "== FORMATO DE SALIDA ==" in instruccion or "JSON" in instruccion:
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
                return texto, sobre
            elif resp.status_code in (429, 503):
                ultimo_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                time.sleep(1.0)
                continue  # probar el siguiente modelo de fallback
            else:
                ultimo_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                continue
        except requests.RequestException as e:
            ultimo_error = f"Error de red con {m_cand}: {e}"
            continue

    raise RuntimeError(f"Fallo al invocar Gemini para {para}: {ultimo_error}")
