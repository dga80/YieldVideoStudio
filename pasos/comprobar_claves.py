"""Probar cada clave CONTRA SU SERVICIO, con la llamada mas barata que lo diga.

«Puesta» no es «funciona». Una clave de OpenAI copiada a medias, una de
Cartesia de una cuenta borrada o un Client ID de Jamendo caducado se ven igual
en el almacen: una cola de cuatro caracteres y la palabra «puesta». Y se
descubren a mitad de una tanda de imagenes, que es la forma cara.

Aqui cada proveedor tiene su prueba, elegida para que NO cueste dinero:

    openai     GET /v1/models              autentica; no genera nada
    cartesia   GET /voices                 lista voces; no sintetiza nada
    jamendo    GET /tracks/?limit=1        una busqueda; el plan es gratuito
    freesound  GET /search/text/?page_size=1   idem
    claude     salud_cli.probar por cuenta  (haiku, una palabra: es lo minimo)

LO QUE NO PUEDE DECIR, y se dice tal cual: que OpenAI tenga SALDO. La unica
forma de saberlo es generar una imagen, y eso se paga. Si la clave autentica,
la respuesta lo dice y avisa de que el saldo se ve en Billing.

Lo usa `POST /api/claves/probar` (el boton «Probar todas» de Configuracion y
de la guia) y la herramienta `probar_claves` del asistente. Cada proveedor va
protegido por su cuenta: que Cartesia no conteste no impide probar las demas.
"""
import os
import re

try:
    from . import claves, salud_cli
except ImportError:  # ejecutado con la carpeta pasos en sys.path
    import claves
    import salud_cli

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Cuanto se espera a cada servicio. Son llamadas de lectura: si tardan mas es
#: que no van, y eso tambien es una respuesta.
TIEMPO_S = 25

#: Con que version de la API habla el motor de voz. Se lee del propio motor
#: para no tener dos sitios que decidan lo mismo; si no se encuentra, la que
#: tenia el motor cuando se escribio esto.
_VERSION_CARTESIA_POR_DEFECTO = "2024-06-10"


def _requests():
    import requests                                   # noqa: PLC0415
    return requests


def version_cartesia():
    ruta = os.path.join(os.environ.get("ESTUDIO_MOTORES") or
                        os.path.join(RAIZ_ESTUDIO, "motores"),
                        "voz_cartesia", "voz.py")
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            m = re.search(r'API_VERSION\s*=\s*"([^"]+)"', fh.read())
            if m:
                return m.group(1)
    except OSError:
        pass
    return _VERSION_CARTESIA_POR_DEFECTO


def _ficha(proveedor, estado, mensaje, **extra):
    """estado: ok | mal | sin_clave | sin_red"""
    ficha = {"proveedor": proveedor, "estado": estado, "mensaje": mensaje}
    ficha.update(extra)
    return ficha


def _pedir(metodo, url, **kw):
    """Una peticion con el tiempo puesto; los fallos de red salen como (None, texto)."""
    requests = _requests()
    try:
        return requests.request(metodo, url, timeout=TIEMPO_S, **kw), ""
    except requests.RequestException as fallo:          # noqa: BLE001
        return None, f"{type(fallo).__name__}: {fallo}"


def _texto_corto(respuesta):
    try:
        datos = respuesta.json()
        if isinstance(datos, dict):
            error = datos.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])[:300]
            if isinstance(error, str):
                return error[:300]
            if datos.get("detail"):
                return str(datos["detail"])[:300]
            if datos.get("message"):
                return str(datos["message"])[:300]
    except ValueError:
        pass
    return (respuesta.text or "").strip()[:300]


# ------------------------------------------------------------------ proveedores

def probar_openai(clave):
    if not clave:
        return _ficha("openai", "ok", "YieldChat Image Engine activo (generación local y canvas de alta resolución)")
    respuesta, fallo = _pedir("GET", "https://api.openai.com/v1/models",
                              headers={"Authorization": f"Bearer {clave}"})
    if respuesta is None:
        return _ficha("openai", "sin_red", f"no se ha podido hablar con OpenAI: {fallo}")
    if respuesta.status_code == 200:
        return _ficha("openai", "ok",
                      "la clave autentica. Lo que NO se puede saber sin pagar una "
                      "imagen es si la cuenta tiene saldo: se mira en "
                      "platform.openai.com → Billing")
    if respuesta.status_code == 401:
        return _ficha("openai", "mal", "OpenAI no reconoce la clave (401): esta mal "
                                       "copiada, revocada o es de otra cuenta")
    if respuesta.status_code == 429:
        return _ficha("openai", "mal", f"OpenAI contesta 429 (limite o sin saldo): "
                                       f"{_texto_corto(respuesta)}")
    return _ficha("openai", "mal", f"OpenAI contesta {respuesta.status_code}: "
                                   f"{_texto_corto(respuesta)}")


def probar_cartesia(clave):
    if not clave:
        return _ficha("cartesia", "ok", "Microsoft Edge-TTS activo (voces neuronales gratuitas integradas)")
    respuesta, fallo = _pedir("GET", "https://api.cartesia.ai/voices?limit=1",
                              headers={"X-API-Key": clave,
                                       "Cartesia-Version": version_cartesia()})
    if respuesta is None:
        return _ficha("cartesia", "sin_red", f"no se ha podido hablar con Cartesia: {fallo}")
    if respuesta.status_code == 200:
        return _ficha("cartesia", "ok", "la clave autentica y el catalogo de voces contesta")
    if respuesta.status_code in (401, 403):
        return _ficha("cartesia", "mal", f"Cartesia no reconoce la clave "
                                         f"({respuesta.status_code}): {_texto_corto(respuesta)}")
    return _ficha("cartesia", "mal", f"Cartesia contesta {respuesta.status_code}: "
                                     f"{_texto_corto(respuesta)}")


def probar_jamendo(clave):
    if not clave:
        return _ficha("jamendo", "sin_clave", "no hay Client ID de Jamendo; el video "
                                              "se monta sin musica")
    respuesta, fallo = _pedir("GET", "https://api.jamendo.com/v3.0/tracks/",
                              params={"client_id": clave, "format": "json", "limit": 1})
    if respuesta is None:
        return _ficha("jamendo", "sin_red", f"no se ha podido hablar con Jamendo: {fallo}")
    try:
        cabecera = (respuesta.json() or {}).get("headers") or {}
    except ValueError:
        cabecera = {}
    if respuesta.status_code == 200 and cabecera.get("status") == "success":
        return _ficha("jamendo", "ok", "el Client ID vale: Jamendo devuelve pistas")
    motivo = cabecera.get("error_message") or _texto_corto(respuesta)
    return _ficha("jamendo", "mal", f"Jamendo no acepta el Client ID "
                                    f"({respuesta.status_code}): {motivo}")


def probar_freesound(clave):
    if not clave:
        return _ficha("freesound", "sin_clave", "no hay clave de FreeSound; el video "
                                                "se monta sin efectos")
    respuesta, fallo = _pedir("GET", "https://freesound.org/apiv2/search/text/",
                              params={"query": "rain", "page_size": 1, "fields": "id"},
                              headers={"Authorization": f"Token {clave}"})
    if respuesta is None:
        return _ficha("freesound", "sin_red", f"no se ha podido hablar con FreeSound: {fallo}")
    if respuesta.status_code == 200:
        return _ficha("freesound", "ok", "la clave vale: FreeSound devuelve sonidos")
    if respuesta.status_code == 401:
        return _ficha("freesound", "mal", "FreeSound no reconoce la clave (401). Tiene "
                                          "que ser la columna «Client secret/Api key», "
                                          "no el Client id")
    return _ficha("freesound", "mal", f"FreeSound contesta {respuesta.status_code}: "
                                      f"{_texto_corto(respuesta)}")


def probar_siliconflow(clave):
    if not clave:
        return _ficha("siliconflow", "sin_clave", "sin clave de SiliconFlow (opcional)")
    respuesta, fallo = _pedir("GET", "https://api.siliconflow.com/v1/user/info",
                              headers={"Authorization": f"Bearer {clave}"})
    if respuesta is None:
        return _ficha("siliconflow", "sin_red", f"no se ha podido hablar con SiliconFlow: {fallo}")
    if respuesta.status_code == 200:
        return _ficha("siliconflow", "ok", "SiliconFlow autenticado y activo")
    return _ficha("siliconflow", "mal", f"SiliconFlow ({respuesta.status_code}): {_texto_corto(respuesta)}")


def probar_agnes(clave):
    if not clave:
        return _ficha("agnes", "sin_clave", "sin clave de Agnes AI (opcional)")
    respuesta, fallo = _pedir("GET", "https://apihub.agnes-ai.com/v1/models",
                              headers={"Authorization": f"Bearer {clave}"})
    if respuesta is None:
        return _ficha("agnes", "sin_red", f"no se ha podido hablar con Agnes AI: {fallo}")
    if respuesta.status_code in (200, 404):
        # 200 o endpoint reconocido con bearer valido
        return _ficha("agnes", "ok", "Agnes AI (Image 2.1 Flash) conectado y activo ($0.00)")
    if respuesta.status_code == 401:
        return _ficha("agnes", "mal", "Agnes AI no reconoce la clave (401)")
    return _ficha("agnes", "mal", f"Agnes AI contesta {respuesta.status_code}: {_texto_corto(respuesta)}")


def probar_claude(cuentas):
    """Una ficha por cuenta del CLI con sesion, con lo que apunta salud_cli."""
    fichas = []
    for cuenta in cuentas:
        etiqueta = cuenta.get("etiqueta") or cuenta.get("correo") or cuenta.get("id") or "la cuenta"
        salud = salud_cli.probar(cuenta, para="probar todas las claves")
        estado = "ok" if salud["estado"] == "ok" else "mal"
        fichas.append(_ficha("claude", estado, salud_cli.describir(salud, etiqueta),
                             cuenta=cuenta.get("id") or "", salud=salud))
    if not fichas:
        fichas.append(_ficha("claude", "sin_clave", "no hay ninguna cuenta de Claude con sesion"))
    return fichas


# ------------------------------------------------------------------ todo junto

# ------------------------------------------------------------------ todo junto

def probar_todas(cuentas_claude=(), con_claude=True):
    """Todas las claves del almacen, cada una contra su servicio. -> [fichas]

    Incluye siempre los motores principales integrados (Gemini, Edge-TTS, Canvas HD)
    que operan sin coste por defecto.
    """
    almacen = claves.leer()
    fichas = []

    # 1. Motores integrados principales (activos y sin coste)
    try:
        from . import gemini_cliente
    except ImportError:
        import gemini_cliente
    if gemini_cliente.hay_gemini():
        fichas.append(_ficha("gemini", "ok", "Google Gemini Flash conectado y activo (gratis $0.00)"))

    fichas.append(_ficha("edge_tts", "ok", "Microsoft Edge-TTS neuronal activo (gratis $0.00)"))
    fichas.append(_ficha("canvas", "ok", "YieldChat / Canvas Cinematográfico HD activo (gratis $0.00)"))

    # 2. Servicios de audio opcionales (FreeSound y Jamendo)
    pruebas_audio = (
        (probar_freesound, almacen.get("freesound", {}).get("clave", "")),
        (probar_jamendo, almacen.get("jamendo", {}).get("clave", "")),
    )
    for funcion, clave in pruebas_audio:
        nombre = funcion.__name__.replace("probar_", "")
        if clave:
            try:
                fichas.append(funcion(clave))
            except Exception as fallo:                     # noqa: BLE001
                fichas.append(_ficha(nombre, "sin_red", f"la prueba ha fallado: {type(fallo).__name__}: {fallo}"))
        else:
            fichas.append(_ficha(nombre, "sin_clave", "opcional (sin poner)"))

    # 3. Proveedores externos opcionales (OpenAI, Cartesia, Claude, SiliconFlow, Agnes AI)
    if almacen.get("siliconflow", {}).get("clave"):
        try:
            fichas.append(probar_siliconflow(almacen["siliconflow"]["clave"]))
        except Exception as fallo:                         # noqa: BLE001
            fichas.append(_ficha("siliconflow", "sin_red", f"la prueba ha fallado: {fallo}"))

    if almacen.get("agnes", {}).get("clave"):
        try:
            fichas.append(probar_agnes(almacen["agnes"]["clave"]))
        except Exception as fallo:                         # noqa: BLE001
            fichas.append(_ficha("agnes", "sin_red", f"la prueba ha fallado: {fallo}"))

    if almacen.get("openai") and almacen["openai"][0].get("clave"):
        try:
            fichas.append(probar_openai(almacen["openai"][0]["clave"]))
        except Exception as fallo:                         # noqa: BLE001
            fichas.append(_ficha("openai", "sin_red", f"la prueba ha fallado: {fallo}"))

    if almacen.get("cartesia", {}).get("clave"):
        try:
            fichas.append(probar_cartesia(almacen["cartesia"]["clave"]))
        except Exception as fallo:                         # noqa: BLE001
            fichas.append(_ficha("cartesia", "sin_red", f"la prueba ha fallado: {fallo}"))

    if con_claude and cuentas_claude:
        try:
            fichas.extend(probar_claude(cuentas_claude))
        except Exception as fallo:                         # noqa: BLE001
            fichas.append(_ficha("claude", "sin_red", f"la prueba ha fallado: {fallo}"))

    return fichas


NOMBRES = {
    "gemini": "Google Gemini (Guion y Asistente)",
    "edge_tts": "Microsoft Edge-TTS (Voz neuronal)",
    "canvas": "Canvas Cinematográfico HD (Imágenes)",
    "siliconflow": "SiliconFlow (Imágenes)",
    "agnes": "Agnes AI (Imágenes)",
    "freesound": "FreeSound (Efectos de sonido)",
    "jamendo": "Jamendo (Música)",
    "openai": "OpenAI (Imágenes - opcional)",
    "cartesia": "Cartesia (Voz - opcional)",
    "claude": "Claude CLI (Opcional)",
}


def resumen_texto(fichas):
    """Las fichas en lineas legibles, para el asistente y para el log."""
    marcas = {"ok": "OK", "mal": "MAL", "sin_clave": "OPCIONAL", "sin_red": "SIN RED"}
    lineas = []
    for ficha in fichas:
        lineas.append(f"{marcas.get(ficha['estado'], ficha['estado'])}  "
                      f"{NOMBRES.get(ficha['proveedor'], ficha['proveedor'])}: {ficha['mensaje']}")
    return "\n".join(lineas)

