"""Adversarial Empirical Stress Test Suite for pasos/inversion_visual.py.

Empirical verification of:
1. Corrupted, truncated, random binary noise, and huge image files.
2. Emergency canvas detection and border perturbation tolerance.
3. Malformed, truncated, conversational, and hostile vision responses.
4. Non-existent, corrupted, null-field, and path-traversal preset IDs.
5. Corrupted, incomplete, and hostile cache files (verifying cache integrity guards).
6. Non-string, null, and adversarial character arguments.
7. Concurrent multi-threaded execution.
8. Strict invariant oracles for StyleDNA and CharacterAnchors schemas.
"""

import concurrent.futures
import copy
import json
import os
import re
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

import pasos.inversion_visual as iv


HEX_COLOR_REGEX = re.compile(r"^#[0-9a-fA-F]{6}$")

REQUIRED_DNA_KEYS = {
    "medium",
    "palette_hex",
    "palette_desc",
    "linework",
    "texture",
    "lighting_style",
    "negative_style",
    "dna_block",
}


def assert_dna_schema_invariant(test_case: unittest.TestCase, dna: dict, context_msg: str = ""):
    """Invariant oracle asserting strict conformance to Style DNA contract."""
    test_case.assertIsInstance(dna, dict, f"Return value must be dict. Context: {context_msg}")
    for key in REQUIRED_DNA_KEYS:
        test_case.assertIn(key, dna, f"Missing required key '{key}'. Context: {context_msg}")

    string_keys = ["medium", "palette_desc", "linework", "texture", "lighting_style", "negative_style", "dna_block"]
    for k in string_keys:
        test_case.assertIsInstance(dna[k], str, f"Key '{k}' must be str. Context: {context_msg}")
        test_case.assertTrue(len(dna[k].strip()) > 0, f"Key '{k}' must not be empty. Context: {context_msg}")

    test_case.assertIsInstance(dna["palette_hex"], list, f"'palette_hex' must be list. Context: {context_msg}")
    test_case.assertGreaterEqual(len(dna["palette_hex"]), 1, f"'palette_hex' must have >= 1 color. Context: {context_msg}")
    for hex_code in dna["palette_hex"]:
        test_case.assertIsInstance(hex_code, str, f"Hex color must be str. Context: {context_msg}")
        test_case.assertRegex(hex_code, HEX_COLOR_REGEX, f"Invalid hex color '{hex_code}'. Context: {context_msg}")


def assert_character_schema_invariant(test_case: unittest.TestCase, anchors: dict, context_msg: str = ""):
    """Invariant oracle asserting strict conformance to Character Anchors contract."""
    test_case.assertIsInstance(anchors, dict, f"Return value must be dict. Context: {context_msg}")
    test_case.assertIn("name", anchors, f"Missing key 'name'. Context: {context_msg}")
    test_case.assertIn("anchors_block", anchors, f"Missing key 'anchors_block'. Context: {context_msg}")
    test_case.assertIsInstance(anchors["name"], str, f"'name' must be str. Context: {context_msg}")
    test_case.assertTrue(len(anchors["name"].strip()) > 0, f"'name' must not be empty. Context: {context_msg}")
    test_case.assertIsInstance(anchors["anchors_block"], str, f"'anchors_block' must be str. Context: {context_msg}")
    test_case.assertTrue(len(anchors["anchors_block"].strip()) > 0, f"'anchors_block' must not be empty. Context: {context_msg}")


class TestStressInversionVisual(unittest.TestCase):

    def setUp(self):
        self.work_dir = tempfile.mkdtemp(prefix="stress_iv_")
        self.banco_dir = os.path.join(self.work_dir, "banco")
        os.makedirs(os.path.join(self.banco_dir, "dna"), exist_ok=True)
        os.makedirs(os.path.join(self.banco_dir, "presets"), exist_ok=True)

        self._orig_banco = iv.BANCO
        iv.BANCO = self.banco_dir

        # Valid reference image with distinct unique content
        self.valid_img_path = os.path.join(self.work_dir, "valid_sample.png")
        img = Image.new("RGB", (200, 200), (100, 150, 200))
        d = ImageDraw.Draw(img)
        d.rectangle([(20, 20), (180, 180)], fill=(220, 80, 50))
        img.save(self.valid_img_path, format="PNG")

    def tearDown(self):
        iv.BANCO = self._orig_banco
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def _crear_imagen_unica(self, nombre: str, r: int = 100, g: int = 100, b: int = 100) -> str:
        p = os.path.join(self.work_dir, nombre)
        img = Image.new("RGB", (100, 100), (r, g, b))
        img.save(p, format="PNG")
        return p

    # =========================================================================
    # SUITE 1: Image Corruption & Boundary Stress
    # =========================================================================

    def test_stress_01_zero_byte_file(self):
        """0-byte file must be rejected with ValueError if no preset, or use preset fallback if provided."""
        zero_path = os.path.join(self.work_dir, "zero.png")
        with open(zero_path, "wb") as f:
            pass
        valida, motivo = iv.validar_imagen(zero_path)
        self.assertFalse(valida)
        self.assertEqual(motivo, "fichero_vacio_0_bytes")

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(zero_path)

        dna = iv.extraer_adn_estilo(zero_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "0-byte file input with preset")

        with self.assertRaises(ValueError):
            iv.extraer_anclas_personaje(zero_path, "Marcus")

    def test_stress_02_single_byte_file(self):
        """1-byte file must be rejected as too small without crash."""
        one_byte_path = os.path.join(self.work_dir, "one_byte.png")
        with open(one_byte_path, "wb") as f:
            f.write(b"\x89")
        valida, motivo = iv.validar_imagen(one_byte_path)
        self.assertFalse(valida)
        self.assertEqual(motivo, "fichero_demasiado_pequeno")

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(one_byte_path)

        dna = iv.extraer_adn_estilo(one_byte_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "1-byte file with preset")

    def test_stress_03_truncated_png_header(self):
        """Truncated PNG header (<100 bytes) must be rejected."""
        trunc_path = os.path.join(self.work_dir, "trunc.png")
        with open(trunc_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        valida, motivo = iv.validar_imagen(trunc_path)
        self.assertFalse(valida)
        self.assertEqual(motivo, "fichero_demasiado_pequeno")

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(trunc_path)

        dna = iv.extraer_adn_estilo(trunc_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "truncated PNG header with preset")

    def test_stress_04_corrupted_png_magic_bytes_over_100_bytes(self):
        """File > 100 bytes with corrupted header must be caught by PIL verify."""
        corrupt_path = os.path.join(self.work_dir, "corrupt_magic.png")
        with open(corrupt_path, "wb") as f:
            f.write(b"CORRUPTED_PNG_HEADER_" + os.urandom(200))
        valida, motivo = iv.validar_imagen(corrupt_path)
        self.assertFalse(valida)
        self.assertIn("corrupcion_pil", motivo)

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(corrupt_path)

        dna = iv.extraer_adn_estilo(corrupt_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "corrupted magic bytes with preset")

    def test_stress_05_random_binary_garbage_1mb(self):
        """1 MB of pure random binary noise named as PNG."""
        noise_path = os.path.join(self.work_dir, "noise_1mb.png")
        with open(noise_path, "wb") as f:
            f.write(os.urandom(1024 * 1024))
        valida, motivo = iv.validar_imagen(noise_path)
        self.assertFalse(valida)

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(noise_path)

        dna = iv.extraer_adn_estilo(noise_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "1MB random noise with preset")

        with self.assertRaises(ValueError):
            iv.extraer_anclas_personaje(noise_path, "Elena")

    def test_stress_06_tiny_dimensions_below_16x16(self):
        """Valid PNG with dimensions 8x8 must be rejected by validar_imagen."""
        tiny_path = os.path.join(self.work_dir, "tiny_8x8.png")
        im = Image.new("RGB", (8, 8), (255, 0, 0))
        im.save(tiny_path, format="PNG")
        valida, motivo = iv.validar_imagen(tiny_path)
        self.assertFalse(valida)
        self.assertIn(motivo, ["dimensiones_invalidas", "fichero_demasiado_pequeno"])

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(tiny_path)

        dna = iv.extraer_adn_estilo(tiny_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "8x8 tiny image with preset")

    def test_stress_07_emergency_canvas_exact_border(self):
        """Emergency canvas with signature gold border (212, 175, 55, 120) must be detected and rejected."""
        em_path = os.path.join(self.work_dir, "emergency.png")
        im = Image.new("RGBA", (200, 200), (20, 25, 35, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([(24, 24), (175, 175)], outline=(212, 175, 55, 120), width=2)
        im.save(em_path, format="PNG")

        valida, motivo = iv.validar_imagen(em_path)
        self.assertFalse(valida)
        self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(em_path)

        dna = iv.extraer_adn_estilo(em_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "emergency canvas with preset")

    def test_stress_08_emergency_canvas_rgb_border_perturbation(self):
        """Border with slight +/- 10 RGB perturbation within tolerance (+/- 25) must also be caught."""
        em_path = os.path.join(self.work_dir, "emergency_perturb.png")
        im = Image.new("RGB", (200, 200), (20, 25, 35))
        d = ImageDraw.Draw(im)
        d.rectangle([(24, 24), (175, 175)], outline=(215, 170, 60), width=2)
        im.save(em_path, format="PNG")

        valida, motivo = iv.validar_imagen(em_path)
        self.assertFalse(valida)
        self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(em_path)

        dna = iv.extraer_adn_estilo(em_path, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "emergency canvas with preset")

    def test_stress_09_nonexistent_file_path(self):
        """Non-existent path must be rejected with ValueError or use preset fallback."""
        no_file = os.path.join(self.work_dir, "non_existent_file_123456.png")
        valida, motivo = iv.validar_imagen(no_file)
        self.assertFalse(valida)
        self.assertEqual(motivo, "fichero_no_existe")

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(no_file)

        dna = iv.extraer_adn_estilo(no_file, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "non-existent path with preset")

    def test_stress_10_directory_passed_as_image_path(self):
        """Directory path passed instead of file must be rejected with ValueError or use preset fallback."""
        valida, motivo = iv.validar_imagen(self.work_dir)
        self.assertFalse(valida)
        self.assertEqual(motivo, "fichero_no_existe")

        with self.assertRaises(ValueError):
            iv.extraer_adn_estilo(self.work_dir)

        dna = iv.extraer_adn_estilo(self.work_dir, preset_id="pr1a0eef81dc7")
        assert_dna_schema_invariant(self, dna, "directory path with preset")

    def test_stress_11_invalid_type_inputs(self):
        """Non-string types (None, int, list, dict, bool) passed as ruta_lamina must not crash."""
        for bad_input in [12345, [], {}, True, 3.14]:
            valida, motivo = iv.validar_imagen(bad_input)
            self.assertFalse(valida)
            self.assertEqual(motivo, "ruta_invalida_o_vacia")
            with self.assertRaises(ValueError):
                iv.extraer_adn_estilo(bad_input)

        valida, motivo = iv.validar_imagen(None)
        self.assertFalse(valida)
        self.assertEqual(motivo, "ruta_invalida_o_vacia")
        dna = iv.extraer_adn_estilo(None)
        assert_dna_schema_invariant(self, dna, "None input returns default style DNA")

    def test_stress_12_special_characters_in_filename(self):
        """Files with spaces, accents, and unicode symbols."""
        special_path = os.path.join(self.work_dir, "lámina con espacios y ñ_🔥.png")
        shutil.copyfile(self.valid_img_path, special_path)
        valida, motivo = iv.validar_imagen(special_path)
        self.assertTrue(valida)

    # =========================================================================
    # SUITE 2: Malformed Vision Response Handling (Gemini Vision Mocking)
    # =========================================================================

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_13_vision_returns_empty_string(self, mock_hay, mock_ejecutar):
        """Empty string returned from vision API must trigger fallback."""
        img = self._crear_imagen_unica("img13.png", 10, 20, 30)
        mock_ejecutar.return_value = ("", {})
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "empty vision response")

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_14_vision_raises_network_exception(self, mock_hay, mock_ejecutar):
        """Network exception in gemini_cliente.ejecutar must not crash caller."""
        img = self._crear_imagen_unica("img14.png", 40, 50, 60)
        mock_ejecutar.side_effect = ConnectionResetError("Connection dropped by peer")
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "vision network exception")

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_15_vision_returns_conversational_text_no_json(self, mock_hay, mock_ejecutar):
        """Conversational response without JSON triggers fallback."""
        img = self._crear_imagen_unica("img15.png", 70, 80, 90)
        mock_ejecutar.return_value = ("I cannot analyze this image as requested. Please provide another.", {})
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "conversational text no json")

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_16_vision_returns_markdown_wrapped_json(self, mock_hay, mock_ejecutar):
        """Valid JSON wrapped in markdown code fence is correctly parsed."""
        img = self._crear_imagen_unica("img16.png", 11, 22, 33)
        valid_payload = json.dumps({
            "medium": "stylized 2D cel animation",
            "palette_hex": ["#FF0000", "#00FF00", "#0000FF"],
            "palette_desc": "vibrant primary tones",
            "linework": "clean bold dynamic contours",
            "texture": "flat matte cel fills",
            "lighting_style": "high contrast graphic lighting",
            "negative_style": "3d render, realistic photographic",
            "dna_block": "stylized 2D cel animation with clean bold dynamic contours and flat matte fills"
        })
        mock_ejecutar.return_value = (f"```json\n{valid_payload}\n```", {})
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "markdown wrapped json")
        self.assertEqual(dna["medium"], "stylized 2D cel animation")

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_17_vision_returns_incomplete_keys(self, mock_hay, mock_ejecutar):
        """JSON missing 6 of 8 keys must fill missing keys from DEFAULT_STYLE_DNA."""
        img = self._crear_imagen_unica("img17.png", 44, 55, 66)
        incomplete_json = json.dumps({
            "medium": "retro pixel art 16-bit",
            "palette_hex": ["#222222", "#EAEAEA"]
        })
        mock_ejecutar.return_value = (incomplete_json, {})
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "incomplete keys filled")
        self.assertEqual(dna["medium"], "retro pixel art 16-bit")
        self.assertEqual(dna["texture"], iv.DEFAULT_STYLE_DNA["texture"])

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_18_vision_returns_empty_and_null_string_fields(self, mock_hay, mock_ejecutar):
        """JSON with empty or whitespace-only string fields replaces them with defaults."""
        img = self._crear_imagen_unica("img18.png", 77, 88, 99)
        empty_fields_json = json.dumps({
            "medium": "",
            "palette_hex": ["#112233"],
            "palette_desc": "   ",
            "linework": None,
            "texture": "",
            "lighting_style": "",
            "negative_style": "",
            "dna_block": ""
        })
        mock_ejecutar.return_value = (empty_fields_json, {})
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "empty string fields replaced")

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_19_vision_returns_malformed_palette_hex_entries(self, mock_hay, mock_ejecutar):
        """Invalid hex strings in palette_hex are sanitized."""
        img = self._crear_imagen_unica("img19.png", 12, 34, 56)
        bad_palette_json = json.dumps({
            "medium": "oil painting on coarse canvas",
            "palette_hex": ["#GGGGGG", "invalid_color", "#123", 12345, "#AABBCC"]
        })
        mock_ejecutar.return_value = (bad_palette_json, {})
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "malformed palette sanitized")
        self.assertIn("#AABBCC", dna["palette_hex"])

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_20_vision_character_returns_empty_or_null_anchors(self, mock_hay, mock_ejecutar):
        """Character response with empty anchors_block automatically generates synthesized fallback."""
        img = self._crear_imagen_unica("img20.png", 65, 43, 21)
        empty_anchors_json = json.dumps({
            "name": "Detective Miller",
            "anchors_block": ""
        })
        mock_ejecutar.return_value = (empty_anchors_json, {})
        char = iv.extraer_anclas_personaje(img, "Detective Miller")
        assert_character_schema_invariant(self, char, "empty anchors fallback")
        self.assertIn("Detective Miller", char["anchors_block"])

    # =========================================================================
    # SUITE 3: Preset Resolution & Fallback Robustness
    # =========================================================================

    def test_stress_21_nonexistent_preset_id(self):
        """Non-existent preset ID must return valid DEFAULT_STYLE_DNA without error."""
        dna = iv.extraer_adn_estilo(ruta_lamina=None, preset_id="pr_nonexistent_id_999")
        assert_dna_schema_invariant(self, dna, "non-existent preset id")

    def test_stress_22_empty_and_whitespace_preset_id(self):
        """Empty string or whitespace preset ID."""
        dna = iv.extraer_adn_estilo(ruta_lamina=None, preset_id="   ")
        assert_dna_schema_invariant(self, dna, "whitespace preset id")

    def test_stress_23_path_traversal_preset_id(self):
        """Hostile path traversal in preset_id does not crash or escape."""
        dna = iv.extraer_adn_estilo(ruta_lamina=None, preset_id="../../etc/passwd")
        assert_dna_schema_invariant(self, dna, "path traversal preset id")

    def test_stress_24_sintetizar_adn_with_null_fields_in_presets_json(self):
        """Test synthesizing DNA when presets.json contains None for acabado/guia/paleta/trazo/luz/evitar."""
        with patch("pasos.inversion_visual.leer_json") as mock_leer:
            mock_leer.return_value = {
                "presets": [
                    {
                        "id": "pr_null_test",
                        "datos": {
                            "estilo": {
                                "guia": {
                                    "acabado": None,
                                    "guia": None,
                                    "paleta": None,
                                    "trazo": None,
                                    "relleno": None,
                                    "luz": None,
                                    "evitar": None
                                }
                            }
                        }
                    }
                ]
            }
            try:
                dna = iv.sintetizar_adn_desde_preset("pr_null_test")
                assert_dna_schema_invariant(self, dna, "preset with null fields")
            except AttributeError as ae:
                self.fail(f"VULNERABILITY CONFIRMED: AttributeError on null guia fields in sintetizar_adn_desde_preset: {ae}")

    # =========================================================================
    # SUITE 4: Cache Subsystem Resilience
    # =========================================================================

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_25_corrupted_json_in_dna_cache(self, mock_hay, mock_ejecutar):
        """Corrupted JSON in banco/dna/estilo_{huella}.json must be ignored and recomputed."""
        img = self._crear_imagen_unica("img25.png", 99, 11, 22)
        huella = iv.huella_fichero(img)
        cache_path = os.path.join(self.banco_dir, "dna", f"estilo_{huella}.json")
        with open(cache_path, "w") as f:
            f.write("{ INVALID JSON CORRUPTED FILE !!!")

        mock_ejecutar.return_value = (json.dumps({
            "medium": "clean vector",
            "palette_hex": ["#111111", "#222222"],
            "palette_desc": "dark",
            "linework": "fine",
            "texture": "flat",
            "lighting_style": "ambient",
            "negative_style": "3d",
            "dna_block": "clean vector fine lines"
        }), {})

        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "corrupted cache file ignored")

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_stress_26_cache_with_empty_strings_ignored(self, mock_hay, mock_ejecutar):
        """Cache file containing empty strings must fail _es_adn_valido and not poison results."""
        img = self._crear_imagen_unica("img26.png", 33, 44, 55)
        huella = iv.huella_fichero(img)
        cache_path = os.path.join(self.banco_dir, "dna", f"estilo_{huella}.json")
        poisoned_cache = copy.deepcopy(iv.DEFAULT_STYLE_DNA)
        poisoned_cache["medium"] = ""
        with open(cache_path, "w") as f:
            json.dump(poisoned_cache, f)

        mock_ejecutar.return_value = (json.dumps(iv.DEFAULT_STYLE_DNA), {})
        dna = iv.extraer_adn_estilo(img)
        assert_dna_schema_invariant(self, dna, "poisoned cache rejected")
        self.assertTrue(len(dna["medium"].strip()) > 0)

    def test_stress_27_character_cache_with_empty_anchors_block(self):
        """Character cache with empty anchors_block: does extraer_anclas_personaje reject it or return empty?"""
        img = self._crear_imagen_unica("img27.png", 66, 77, 88)
        huella = iv.huella_fichero(img)
        cache_path = os.path.join(self.banco_dir, "dna", f"personaje_{huella}.json")
        with open(cache_path, "w") as f:
            json.dump({"name": "TestChar", "anchors_block": ""}, f)

        char = iv.extraer_anclas_personaje(img, "TestChar")
        try:
            assert_character_schema_invariant(self, char, "character cache with empty anchors")
        except AssertionError as ae:
            self.fail(f"VULNERABILITY CONFIRMED: Character cache returned empty anchors_block: {ae}")

    # =========================================================================
    # SUITE 5: Character Anchor Argument Stress
    # =========================================================================

    def test_stress_28_character_none_and_empty_name(self):
        """None or empty string for nombre_personaje defaults cleanly to 'character'."""
        img = self._crear_imagen_unica("img28.png", 101, 102, 103)
        c1 = iv.extraer_anclas_personaje(img, None)
        assert_character_schema_invariant(self, c1, "character None name")
        self.assertEqual(c1["name"], "character")

        c2 = iv.extraer_anclas_personaje(img, "")
        assert_character_schema_invariant(self, c2, "character empty name")
        self.assertEqual(c2["name"], "character")

    def test_stress_29_character_non_string_fallback_description(self):
        """If descripcion_fallback is not a string (e.g. integer 123 or list), must not crash."""
        img = self._crear_imagen_unica("img29.png", 104, 105, 106)
        try:
            c = iv.extraer_anclas_personaje(img, "Marcus", descripcion_fallback=12345)
            assert_character_schema_invariant(self, c, "non-string fallback description")
        except AttributeError as ae:
            self.fail(f"VULNERABILITY CONFIRMED: AttributeError on non-string descripcion_fallback: {ae}")

    # =========================================================================
    # SUITE 6: Concurrency & Paleta Utility Stress
    # =========================================================================

    def test_stress_30_describir_paleta_hex_non_string_elements(self):
        """describir_paleta_hex must not crash if passed non-string elements."""
        try:
            res = iv.describir_paleta_hex([None, 123, "#FF0000", True])
            self.assertIsInstance(res, str)
        except AttributeError as ae:
            self.fail(f"VULNERABILITY CONFIRMED: AttributeError in describir_paleta_hex on non-string element: {ae}")

    def test_stress_31_concurrent_threads_extraer_adn(self):
        """10 concurrent threads invoking extraer_adn_estilo simultaneously with pre-seeded cache."""
        img = self._crear_imagen_unica("img31.png", 107, 108, 109)
        huella = iv.huella_fichero(img)
        cache_path = os.path.join(self.banco_dir, "dna", f"estilo_{huella}.json")
        with open(cache_path, "w") as f:
            json.dump(iv.DEFAULT_STYLE_DNA, f)

        def _invoke(idx):
            return iv.extraer_adn_estilo(img)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_invoke, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 10)
        for r in results:
            assert_dna_schema_invariant(self, r, "concurrent thread invocation")


if __name__ == "__main__":
    unittest.main()
