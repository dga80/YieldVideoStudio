"""Control de calidad visual y juez adversarial para AS Video Studio.

Verificación programática con OpenCV y NumPy:
- Detección de lienzos de emergencia (borde dorado 212, 175, 55 o baja varianza cromática).
- Medición de fidelidad cromática respecto a la lámina de estilo mediante distancia de Bhattacharyya (HSV).
- Verificación de proporciones y cumplimiento de encuadre (16:9, 9:16, 1:1).
"""
import io
import os
import cv2
import numpy as np
from PIL import Image


def auditar_imagen_generada(
    ruta_o_bytes_imagen: str | bytes,
    ruta_referencia_estilo: str = None,
    encuadre_esperado: str = None
) -> dict:
    """Audita una imagen generada frente a contratos de fidelidad visual y calidad.

    Returns:
        dict con:
        {
            "es_valida": bool,
            "es_lienzo_emergencia": bool,
            "distancia_histograma_bhattacharyya": float,
            "cumple_estilo": bool,
            "cumple_encuadre": bool,
            "detalles": list[str]
        }
    """
    detalles = []

    # 1. Cargar bytes de la imagen
    if isinstance(ruta_o_bytes_imagen, str):
        if not os.path.isfile(ruta_o_bytes_imagen):
            return {
                "es_valida": False,
                "es_lienzo_emergencia": False,
                "distancia_histograma_bhattacharyya": 1.0,
                "cumple_estilo": False,
                "cumple_encuadre": False,
                "detalles": [f"Archivo no encontrado: {ruta_o_bytes_imagen}"]
            }
        try:
            with open(ruta_o_bytes_imagen, "rb") as fh:
                raw_bytes = fh.read()
        except Exception as exc:
            return {
                "es_valida": False,
                "es_lienzo_emergencia": False,
                "distancia_histograma_bhattacharyya": 1.0,
                "cumple_estilo": False,
                "cumple_encuadre": False,
                "detalles": [f"Error de lectura: {exc}"]
            }
    else:
        raw_bytes = ruta_o_bytes_imagen

    if not raw_bytes or len(raw_bytes) < 8 or not raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return {
            "es_valida": False,
            "es_lienzo_emergencia": False,
            "distancia_histograma_bhattacharyya": 1.0,
            "cumple_estilo": False,
            "cumple_encuadre": False,
            "detalles": ["Bytes inválidos o no corresponden a formato PNG"]
        }

    try:
        pil_im = Image.open(io.BytesIO(raw_bytes))
        w, h = pil_im.size
    except Exception as exc:
        return {
            "es_valida": False,
            "es_lienzo_emergencia": False,
            "distancia_histograma_bhattacharyya": 1.0,
            "cumple_estilo": False,
            "cumple_encuadre": False,
            "detalles": [f"Error decodificando imagen PIL: {exc}"]
        }

    # 2. Detección de lienzos de emergencia o ciegos
    es_emergencia = False
    arr_rgba = np.array(pil_im.convert("RGBA"))
    if w > 48 and h > 48:
        border_px = arr_rgba[24, 24:w-24, :3]
        gold = np.array([212, 175, 55])
        diffs = np.linalg.norm(border_px - gold, axis=1)
        if np.mean(diffs < 60) > 0.3:
            es_emergencia = True
            detalles.append("Detectado borde dorado característico de lienzo de emergencia (212, 175, 55)")

    arr_gray = np.array(pil_im.convert("L"))
    variance = float(np.var(arr_gray))
    if variance < 5.0 and not es_emergencia:
        es_emergencia = True
        detalles.append(f"Varianza cromática nula/plana ({variance:.2f}), posible lienzo ciego")

    es_valida = not es_emergencia

    # 3. Verificación de encuadre y relación de aspecto
    cumple_encuadre = True
    aspect_ratio = w / float(h)
    if encuadre_esperado:
        if encuadre_esperado in ("16:9", "apaisado", "general", "aereo", "cenital"):
            if abs(aspect_ratio - (16.0 / 9.0)) > 0.15:
                cumple_encuadre = False
                detalles.append(f"Relación de aspecto {aspect_ratio:.2f} no coincide con 16:9 esperado")
        elif encuadre_esperado in ("9:16", "vertical"):
            if abs(aspect_ratio - (9.0 / 16.0)) > 0.15:
                cumple_encuadre = False
                detalles.append(f"Relación de aspecto {aspect_ratio:.2f} no coincide con 9:16 esperado")
        elif encuadre_esperado in ("1:1", "cuadrado"):
            if abs(aspect_ratio - 1.0) > 0.1:
                cumple_encuadre = False
                detalles.append(f"Relación de aspecto {aspect_ratio:.2f} no coincide con 1:1 esperado")

    # 4. Consistencia cromática e histograma frente a referencia de estilo (Bhattacharyya)
    distancia_bhattacharyya = 0.0
    cumple_estilo = True
    if ruta_referencia_estilo and os.path.isfile(ruta_referencia_estilo):
        try:
            ref_bgr = cv2.imread(ruta_referencia_estilo)
            cur_bgr = cv2.cvtColor(np.array(pil_im.convert("RGB")), cv2.COLOR_RGB2BGR)
            if ref_bgr is not None and cur_bgr is not None:
                hsv_ref = cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2HSV)
                hsv_cur = cv2.cvtColor(cur_bgr, cv2.COLOR_BGR2HSV)

                # Histograma 2D Hue-Saturation
                hist_hs_ref = cv2.calcHist([hsv_ref], [0, 1], None, [30, 32], [0, 180, 0, 256])
                hist_hs_cur = cv2.calcHist([hsv_cur], [0, 1], None, [30, 32], [0, 180, 0, 256])
                cv2.normalize(hist_hs_ref, hist_hs_ref, 0, 1, cv2.NORM_MINMAX)
                cv2.normalize(hist_hs_cur, hist_hs_cur, 0, 1, cv2.NORM_MINMAX)
                dist_hs = cv2.compareHist(hist_hs_ref, hist_hs_cur, cv2.HISTCMP_BHATTACHARYYA)

                # Histograma 1D Value
                hist_v_ref = cv2.calcHist([hsv_ref], [2], None, [16], [0, 256])
                hist_v_cur = cv2.calcHist([hsv_cur], [2], None, [16], [0, 256])
                cv2.normalize(hist_v_ref, hist_v_ref, 0, 1, cv2.NORM_MINMAX)
                cv2.normalize(hist_v_cur, hist_v_cur, 0, 1, cv2.NORM_MINMAX)
                dist_v = cv2.compareHist(hist_v_ref, hist_v_cur, cv2.HISTCMP_BHATTACHARYYA)

                s_mean = (float(np.mean(hsv_ref[:, :, 1])) + float(np.mean(hsv_cur[:, :, 1]))) / 2.0
                if s_mean < 15.0:
                    dist = dist_v
                else:
                    dist = 0.8 * dist_hs + 0.2 * dist_v

                distancia_bhattacharyya = float(np.clip(dist, 0.0, 1.0))
                cumple_estilo = (distancia_bhattacharyya < 0.65)
                if not cumple_estilo:
                    detalles.append(f"Distancia Bhattacharyya ({distancia_bhattacharyya:.3f}) excede umbral 0.65")
        except Exception as exc:
            detalles.append(f"Error calculando distancia de histograma: {exc}")
            distancia_bhattacharyya = 1.0
            cumple_estilo = False

    return {
        "es_valida": es_valida,
        "es_lienzo_emergencia": es_emergencia,
        "distancia_histograma_bhattacharyya": distancia_bhattacharyya,
        "cumple_estilo": cumple_estilo,
        "cumple_encuadre": cumple_encuadre,
        "detalles": detalles
    }
