"""Prueba unitaria y de integración para pasos/inversion_visual.py.

Verifica:
1. Cumplimiento estricto del contrato de interfaz (PROJECT.md § Interface Contracts):
   - extraer_adn_estilo(ruta_lamina, preset_id=None) -> dict con 8 claves obligatorias.
   - extraer_anclas_personaje(ruta_personaje, nombre_personaje) -> dict con name y anchors_block.
2. Fallback heurístico determinista cuando Gemini Vision no está disponible:
   - Extracción desde presets.json (Pluma_2, Pluma_3, Cartoon_Stick, androides).
   - Inferencia automática del preset_id desde la ruta.
   - Fallback a DEFAULT_STYLE_DNA ante presets inexistentes o vacíos.
3. Tratamiento robusto de referencias corruptas, inexistentes o lienzos de emergencia:
   - Rutas None o vacías.
   - Ficheros de 0 bytes o truncados con bytes basura.
   - Detección de lienzos de emergencia (12-16 KB con borde dorado (212, 175, 55, 120)).
4. Resiliencia ante fallos de red / cuota (HTTP 429 / timeouts) sin lanzar excepciones no controladas.
5. Inversión multimodal Gemini Vision exitosa (mock) y caching de contenido por SHA-256.
6. Algoritmo de mapeo cromático determinista (RGB Euclidiano).
"""
import copy
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from pasos import inversion_visual


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


class BaseInversionVisualTestCase(unittest.TestCase):
    """Base para pruebas de inversión visual con aislamiento completo de BANCO."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_inversion_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(self.banco_dir, exist_ok=True)
        self.patcher_banco = patch("pasos.inversion_visual.BANCO", self.banco_dir)
        self.patcher_banco.start()

    def tearDown(self):
        self.patcher_banco.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class TestInversionVisualContrato(BaseInversionVisualTestCase):
    """Verificación de contratos y esquemas según PROJECT.md § Interface Contracts."""

    def test_contrato_adn_estilo_claves_y_tipos(self):
        """Verifica que extraer_adn_estilo devuelva exactamente las 8 claves y tipos correctos."""
        adn = inversion_visual.extraer_adn_estilo(None, preset_id="pr1a0eef81dc7")
        self.assertIsInstance(adn, dict)
        self.assertEqual(set(adn.keys()), CLAVES_ADN_ESPERADAS)
        self.assertIsInstance(adn["medium"], str)
        self.assertTrue(len(adn["medium"]) > 0)
        self.assertIsInstance(adn["palette_hex"], list)
        self.assertTrue(len(adn["palette_hex"]) > 0)
        for h in adn["palette_hex"]:
            self.assertRegex(h, r"^#[0-9a-fA-F]{6}$")
        self.assertIsInstance(adn["palette_desc"], str)
        self.assertIsInstance(adn["linework"], str)
        self.assertIsInstance(adn["texture"], str)
        self.assertIsInstance(adn["lighting_style"], str)
        self.assertIsInstance(adn["negative_style"], str)
        self.assertIsInstance(adn["dna_block"], str)

    def test_contrato_anclas_personaje(self):
        """Verifica que extraer_anclas_personaje devuelva name y anchors_block."""
        res = inversion_visual.extraer_anclas_personaje(None, "juan_el_pastor")
        self.assertIsInstance(res, dict)
        self.assertIn("name", res)
        self.assertIn("anchors_block", res)
        self.assertEqual(res["name"], "juan_el_pastor")
        self.assertIsInstance(res["anchors_block"], str)
        self.assertTrue(len(res["anchors_block"]) > 0)


class TestInversionVisualFallbackHeuristico(BaseInversionVisualTestCase):
    """Verificación del fallback heurístico determinista desde presets.json."""

    def test_fallback_preset_pluma_2(self):
        adn = inversion_visual.extraer_adn_estilo(None, preset_id="pr1a0eef81dc7")
        self.assertIn("#ffffff", [c.lower() for c in adn["palette_hex"]])
        self.assertIn("#000000", [c.lower() for c in adn["palette_hex"]])
        self.assertTrue(any(w in adn["linework"].lower() for w in ["uniform", "black", "line", "marker"]))

    def test_fallback_preset_pluma_3(self):
        adn = inversion_visual.extraer_adn_estilo(None, preset_id="pr1a0f81fbf25")
        self.assertIn("#000000", [c.lower() for c in adn["palette_hex"]])
        self.assertIn("#ffffff", [c.lower() for c in adn["palette_hex"]])
        self.assertTrue(any(w in adn["medium"].lower() for w in ["vector", "clean", "render"]))

    def test_fallback_preset_cartoon_stick(self):
        adn = inversion_visual.extraer_adn_estilo(None, preset_id="pr1a0f91a4e44")
        self.assertIn("#4a90e2", [c.lower() for c in adn["palette_hex"]])
        self.assertTrue(any(w in adn["linework"].lower() for w in ["outline", "black", "uniform", "pixel"]))

    def test_fallback_preset_androides(self):
        adn = inversion_visual.extraer_adn_estilo(None, preset_id="pr1a10889874e")
        self.assertTrue(any(w in adn["medium"].lower() for w in ["photorealistic", "3d", "chrome"]))
        self.assertTrue(any(w in adn["linework"].lower() for w in ["no", "outlines", "strokes"]))

    def test_inferencia_preset_desde_ruta(self):
        ruta_ficticia = "/var/banco/presets/pr1a0f91a4e44/00_cara.png"
        adn = inversion_visual.extraer_adn_estilo(ruta_ficticia, preset_id=None)
        # Cartoon_Stick
        self.assertIn("#4a90e2", [c.lower() for c in adn["palette_hex"]])

    def test_preset_desconocido_retorna_default_sin_error(self):
        adn = inversion_visual.extraer_adn_estilo(None, preset_id="pr_no_existe_1234")
        self.assertEqual(set(adn.keys()), CLAVES_ADN_ESPERADAS)
        self.assertTrue(len(adn["dna_block"]) > 0)


class TestInversionVisualImagenesCorruptasYLienzos(BaseInversionVisualTestCase):
    """Verificación de tolerancia ante imágenes corruptas, vacías y lienzos de emergencia."""

    def test_fichero_cero_bytes(self):
        f = os.path.join(self.tmp_dir, "vacio.png")
        open(f, "wb").close()
        adn = inversion_visual.extraer_adn_estilo(f, preset_id="pr1a0eef81dc7")
        self.assertEqual(set(adn.keys()), CLAVES_ADN_ESPERADAS)

    def test_fichero_corrupto(self):
        f = os.path.join(self.tmp_dir, "corrupto.png")
        with open(f, "wb") as fh:
            fh.write(b"PNG_HEADER_CORRUPTED_TRUNCATED_DATA_GARBAGE" * 50)
        adn = inversion_visual.extraer_adn_estilo(f, preset_id="pr1a0eef81dc7")
        self.assertEqual(set(adn.keys()), CLAVES_ADN_ESPERADAS)

    def test_rechazo_lienzo_emergencia(self):
        """Un lienzo con borde dorado (212, 175, 55, 120) debe rechazarse antes de la visión."""
        f = os.path.join(self.tmp_dir, "lienzo_emergencia.png")
        img = Image.new("RGBA", (1280, 720), (30, 35, 45, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(24, 24), (1280 - 24, 720 - 24)], outline=(212, 175, 55, 120), width=2)
        img.save(f, "PNG")

        with patch("pasos.gemini_cliente.ejecutar") as mock_ejecutar:
            adn = inversion_visual.extraer_adn_estilo(f, preset_id="pr1a0eef81dc7")
            mock_ejecutar.assert_not_called()
            self.assertEqual(set(adn.keys()), CLAVES_ADN_ESPERADAS)

    def test_personaje_lienzo_emergencia_genera_anclas_limpias(self):
        f = os.path.join(self.tmp_dir, "personaje_lienzo.png")
        img = Image.new("RGBA", (1280, 720), (30, 35, 45, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(24, 24), (1280 - 24, 720 - 24)], outline=(212, 175, 55, 120), width=2)
        img.save(f, "PNG")

        with patch("pasos.gemini_cliente.ejecutar") as mock_ejecutar:
            anclas = inversion_visual.extraer_anclas_personaje(f, "capitan")
            mock_ejecutar.assert_not_called()
            self.assertEqual(anclas["name"], "capitan")
            self.assertIn("capitan", anclas["anchors_block"])


class TestInversionVisualCaosYRed(BaseInversionVisualTestCase):
    """Verificación de tolerancia ante fallos de red y cuota."""

    @patch("pasos.gemini_cliente.ejecutar", side_effect=RuntimeError("HTTP 429: Cuota agotada"))
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_tolerancia_cuota_agotada(self, mock_hay, mock_ejecutar):
        """Si la API lanza 429, el pipeline no debe fallar; debe usar el fallback heurístico."""
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            img = Image.new("RGB", (200, 200), (255, 255, 255))
            img.save(tmp.name, "PNG")
            tmp.close()

            adn = inversion_visual.extraer_adn_estilo(tmp.name, preset_id="pr1a0eef81dc7")
            self.assertEqual(set(adn.keys()), CLAVES_ADN_ESPERADAS)
            self.assertIn("#ffffff", [c.lower() for c in adn["palette_hex"]])
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)


class TestInversionVisualVisionExitosaYCaching(BaseInversionVisualTestCase):
    """Verificación de la invocación multimodal exitosa y reutilización de caché en disco."""

    def test_inversion_vision_mock_exitosa(self):
        """Verifica que una respuesta válida de Gemini Vision se parsee y estructure correctamente."""
        f = os.path.join(self.tmp_dir, "muestra_valida.png")
        img = Image.new("RGB", (300, 300), (100, 150, 200))
        img.save(f, "PNG")

        mock_json_resp = json.dumps({
            "medium": "watercolor and ink wash",
            "palette_hex": ["#6496C8", "#FFFFFF", "#1E1E1E"],
            "palette_desc": "soft sky blue, paper white, ink black",
            "linework": "expressive feathered ink linework with variable pressure",
            "texture": "subtle cold-press paper grain with watercolor blooming",
            "lighting_style": "gentle directional morning daylight with soft shadows",
            "negative_style": "3D render, photorealistic, harsh gradients, glossy reflection",
            "dna_block": "watercolor and ink wash, feathered linework, paper texture, morning light",
        })

        with patch("pasos.gemini_cliente.ejecutar", return_value=(mock_json_resp, {})) as mock_ejecutar:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                adn = inversion_visual.extraer_adn_estilo(f)
                mock_ejecutar.assert_called_once()
                self.assertEqual(adn["medium"], "watercolor and ink wash")
                self.assertIn("#6496C8", adn["palette_hex"])
                self.assertEqual(adn["dna_block"], "watercolor and ink wash, feathered linework, paper texture, morning light")

    def test_cache_hit_evita_segunda_llamada_api(self):
        """Verifica que tras una extracción exitosa, una llamada subsecuente use el caché sin tocar la API."""
        f = os.path.join(self.tmp_dir, "cacheable.png")
        img = Image.new("RGB", (300, 300), (80, 120, 160))
        img.save(f, "PNG")

        mock_json_resp = json.dumps({
            "medium": "flat cel-shaded vector",
            "palette_hex": ["#5078A0", "#FFFFFF", "#000000"],
            "palette_desc": "slate blue, white, black",
            "linework": "clean bold outlines",
            "texture": "solid fills",
            "lighting_style": "ambient flat light",
            "negative_style": "3D, realistic",
            "dna_block": "flat cel-shaded vector with bold outlines",
        })

        with patch("pasos.gemini_cliente.ejecutar", return_value=(mock_json_resp, {})) as mock_ejecutar:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                # Primera llamada: extrae y cachea
                adn1 = inversion_visual.extraer_adn_estilo(f)
                self.assertEqual(mock_ejecutar.call_count, 1)

                # Segunda llamada: debe provenir del caché en disco
                adn2 = inversion_visual.extraer_adn_estilo(f)
                self.assertEqual(mock_ejecutar.call_count, 1)  # No incrementa
                self.assertEqual(adn1["dna_block"], adn2["dna_block"])

    def test_personaje_vision_mock_exitosa(self):
        f = os.path.join(self.tmp_dir, "personaje_valido.png")
        img = Image.new("RGB", (300, 300), (200, 100, 50))
        img.save(f, "PNG")

        mock_json_resp = json.dumps({
            "name": "artemisa",
            "anchors_block": "tall archer with silver braided hair, dark green tunic, golden quiver"
        })

        with patch("pasos.gemini_cliente.ejecutar", return_value=(mock_json_resp, {})) as mock_ejecutar:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                anclas = inversion_visual.extraer_anclas_personaje(f, "artemisa")
                mock_ejecutar.assert_called_once()
                self.assertEqual(anclas["name"], "artemisa")
                self.assertIn("silver braided hair", anclas["anchors_block"])


class TestInversionVisualColorNamer(unittest.TestCase):
    """Verificación del color namer euclidiano."""

    def test_color_namer_determinista(self):
        res = inversion_visual.describir_paleta_hex(["#FFFFFF", "#000000", "#7CC47C", "#3A86FF"])
        self.assertIn("stark white", res)
        self.assertIn("solid black", res)
        self.assertIn("muted sage green", res)
        self.assertIn("electric cobalt blue", res)


if __name__ == "__main__":
    unittest.main()
