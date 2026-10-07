"""
Prueba unitaria y de integración para pasos/inversion_visual.py.

Verifica:
1. Cumplimiento estricto del contrato de interfaz (PROJECT.md):
   - extraer_adn_estilo(ruta_lamina, preset_id=None) -> dict con 8 claves obligatorias.
   - extraer_anclas_personaje(ruta_personaje, nombre_personaje) -> dict con name y anchors_block.
2. Fallback heurístico determinista cuando Gemini Vision no está disponible:
   - Extracción desde presets.json (Pluma_2, Pluma_3, Cartoon_Stick, androides).
   - Inferencia automática del preset_id desde la ruta.
   - Fallback a DEFAULT_STYLE_DNA ante presets inexistentes.
3. Tratamiento robusto de referencias corruptas, inexistentes o lienzos de emergencia:
   - Rutas None o vacías.
   - Ficheros de 0 bytes o truncados.
   - Detección de lienzos de emergencia (12-16 KB con borde dorado (212, 175, 55, 120)).
4. Resiliencia ante fallos de red / cuota (HTTP 429 / timeouts) sin lanzar excepciones no controladas.
"""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

# Se importará desde pasos.inversion_visual una vez implementado
try:
    from pasos import inversion_visual
except ImportError:
    inversion_visual = None


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


class TestInversionVisualContrato(unittest.TestCase):
    """Verificación de contratos y esquemas."""

    def setUp(self):
        if inversion_visual is None:
            self.skipTest("pasos/inversion_visual.py aún no está implementado")

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


class TestInversionVisualFallbackHeuristico(unittest.TestCase):
    """Verificación del fallback heurístico determinista desde presets.json."""

    def setUp(self):
        if inversion_visual is None:
            self.skipTest("pasos/inversion_visual.py aún no está implementado")

    def test_fallback_preset_pluma_2(self):
        adn = inversion_visual.extraer_adn_estilo(None, preset_id="pr1a0eef81dc7")
        self.assertIn("#ffffff", [c.lower() for c in adn["palette_hex"]])
        self.assertIn("#000000", [c.lower() for c in adn["palette_hex"]])
        self.assertTrue(any(w in adn["linework"].lower() for w in ["uniform", "black", "line", "marker"]))

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


class TestInversionVisualImagenesCorruptasYLienzos(unittest.TestCase):
    """Verificación de tolerancia ante imágenes corruptas, vacías y lienzos de emergencia."""

    def setUp(self):
        if inversion_visual is None:
            self.skipTest("pasos/inversion_visual.py aún no está implementado")
        self.tmp_dir = tempfile.mkdtemp(prefix="test_inversion_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

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
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([(24, 24), (1280 - 24, 720 - 24)], outline=(212, 175, 55, 120), width=2)
        img.save(f, "PNG")

        # Mockear gemini_cliente para asegurar que NUNCA se le llama cuando la imagen es un lienzo
        with patch("pasos.gemini_cliente.ejecutar") as mock_ejecutar:
            adn = inversion_visual.extraer_adn_estilo(f, preset_id="pr1a0eef81dc7")
            mock_ejecutar.assert_not_called()
            self.assertEqual(set(adn.keys()), CLAVES_ADN_ESPERADAS)

    def test_personaje_lienzo_emergencia_genera_anclas_limpias(self):
        f = os.path.join(self.tmp_dir, "personaje_lienzo.png")
        img = Image.new("RGBA", (1280, 720), (30, 35, 45, 255))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([(24, 24), (1280 - 24, 720 - 24)], outline=(212, 175, 55, 120), width=2)
        img.save(f, "PNG")

        with patch("pasos.gemini_cliente.ejecutar") as mock_ejecutar:
            anclas = inversion_visual.extraer_anclas_personaje(f, "capitan")
            mock_ejecutar.assert_not_called()
            self.assertEqual(anclas["name"], "capitan")
            self.assertIn("capitan", anclas["anchors_block"])


class TestInversionVisualCaosYRed(unittest.TestCase):
    """Verificación de tolerancia ante fallos de red y cuota."""

    def setUp(self):
        if inversion_visual is None:
            self.skipTest("pasos/inversion_visual.py aún no está implementado")

    @patch("pasos.gemini_cliente.ejecutar", side_effect=RuntimeError("HTTP 429: Cuota agotada"))
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_tolerancia_cuota_agotada(self, mock_hay, mock_ejecutar):
        """Si la API lanza 429, el pipeline no debe fallar; debe usar el fallback heurístico."""
        # Creamos una imagen válida
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


if __name__ == "__main__":
    unittest.main()
