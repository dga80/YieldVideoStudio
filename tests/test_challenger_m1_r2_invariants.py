"""Empirical Invariants, Boundary Safety, and Concurrency Test Suite.

Milestone 1 Iteration 2 (Visual Style & Character DNA Inversion).
Challenger 2 Empirical Challenge Harness.
"""
import concurrent.futures
import copy
import json
import os
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

import pasos.inversion_visual as iv


HEX_REGEX = re.compile(r"^#[0-9a-fA-F]{6}$")
REQUIRED_STYLE_KEYS = [
    "medium",
    "palette_hex",
    "palette_desc",
    "linework",
    "texture",
    "lighting_style",
    "negative_style",
    "dna_block",
]


def assert_style_dna_contract(tc: unittest.TestCase, dna: dict, context: str = ""):
    """Verifies that dna satisfies all 8 keys of Style DNA per PROJECT.md § Interface Contracts."""
    tc.assertIsInstance(dna, dict, f"Style DNA must be dict. [{context}]")
    for k in REQUIRED_STYLE_KEYS:
        tc.assertIn(k, dna, f"Key '{k}' missing from Style DNA. [{context}]")

    # Check non-empty strings
    string_keys = ["medium", "palette_desc", "linework", "texture", "lighting_style", "negative_style", "dna_block"]
    for k in string_keys:
        val = dna[k]
        tc.assertIsInstance(val, str, f"Key '{k}' must be str, got {type(val)}. [{context}]")
        tc.assertTrue(len(val.strip()) > 0, f"Key '{k}' must not be empty or whitespace. [{context}]")

    # Check palette_hex list of valid hex codes
    tc.assertIsInstance(dna["palette_hex"], list, f"'palette_hex' must be list. [{context}]")
    tc.assertGreaterEqual(len(dna["palette_hex"]), 1, f"'palette_hex' must contain >= 1 item. [{context}]")
    for hex_code in dna["palette_hex"]:
        tc.assertIsInstance(hex_code, str, f"Item in 'palette_hex' must be str: {hex_code}. [{context}]")
        tc.assertRegex(hex_code, HEX_REGEX, f"Invalid hex color code: '{hex_code}'. [{context}]")


def assert_character_anchors_contract(tc: unittest.TestCase, anchors: dict, context: str = ""):
    """Verifies that anchors satisfies name and anchors_block per PROJECT.md § Interface Contracts."""
    tc.assertIsInstance(anchors, dict, f"Character anchors must be dict. [{context}]")
    tc.assertIn("name", anchors, f"Key 'name' missing. [{context}]")
    tc.assertIn("anchors_block", anchors, f"Key 'anchors_block' missing. [{context}]")

    tc.assertIsInstance(anchors["name"], str, f"'name' must be str. [{context}]")
    tc.assertTrue(len(anchors["name"].strip()) > 0, f"'name' must not be empty. [{context}]")

    tc.assertIsInstance(anchors["anchors_block"], str, f"'anchors_block' must be str. [{context}]")
    tc.assertTrue(len(anchors["anchors_block"].strip()) > 0, f"'anchors_block' must not be empty. [{context}]")


class TestEmpiricalStyleDNASchemaInvariants(unittest.TestCase):
    """Rigorous verification of Style DNA 8-key schema invariants across all pathways."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="challenger_dna_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(os.path.join(self.banco_dir, "dna"), exist_ok=True)
        os.makedirs(os.path.join(self.banco_dir, "presets"), exist_ok=True)
        self._orig_banco = iv.BANCO
        iv.BANCO = self.banco_dir

        # Create valid test image
        self.valid_img = os.path.join(self.tmp_dir, "style_ref.png")
        im = Image.new("RGB", (256, 256), (240, 240, 240))
        d = ImageDraw.Draw(im)
        d.rectangle([(30, 30), (220, 220)], fill=(70, 130, 180))
        im.save(self.valid_img, format="PNG")

        # Create emergency canvas
        self.emergency_img = os.path.join(self.tmp_dir, "emergency.png")
        im_em = Image.new("RGBA", (100, 100), (20, 25, 35, 255))
        d_em = ImageDraw.Draw(im_em)
        d_em.rectangle([(24, 24), (76, 76)], outline=(212, 175, 55, 120), width=2)
        im_em.save(self.emergency_img, format="PNG")

        # Create corrupt image
        self.corrupt_img = os.path.join(self.tmp_dir, "corrupt.png")
        with open(self.corrupt_img, "wb") as f:
            f.write(b"CORRUPTED_NOT_A_PNG_FILE_DATA_BYTES_EXCEEDING_100_BYTES_" * 5)

        # Create zero byte image
        self.zero_byte_img = os.path.join(self.tmp_dir, "zero.png")
        with open(self.zero_byte_img, "wb") as f:
            pass

    def tearDown(self):
        iv.BANCO = self._orig_banco
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_default_style_dna_constant_conformance(self):
        """DEFAULT_STYLE_DNA must strictly satisfy the 8-key contract."""
        assert_style_dna_contract(self, iv.DEFAULT_STYLE_DNA, "DEFAULT_STYLE_DNA constant")

    def test_no_image_no_preset_returns_compliant_dna(self):
        """extraer_adn_estilo(None, None) must return valid Style DNA."""
        dna = iv.extraer_adn_estilo(ruta_lamina=None, preset_id=None)
        assert_style_dna_contract(self, dna, "no image no preset")

    def test_all_presets_json_entries_synthesis(self):
        """Every preset in presets.json must produce 100% compliant Style DNA."""
        p_path = os.path.join(iv.RAIZ_ESTUDIO, "presets.json")
        if os.path.isfile(p_path):
            with open(p_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            presets = data.get("presets", [])
            self.assertGreater(len(presets), 0, "presets.json must contain at least 1 preset")
            for pr in presets:
                pid = pr.get("id")
                dna = iv.sintetizar_adn_desde_preset(pid)
                assert_style_dna_contract(self, dna, f"preset synthesis for {pid}")

    def test_unknown_or_malformed_preset_id_returns_compliant_dna(self):
        """Invalid, empty, whitespace, and path traversal preset IDs must return compliant DNA."""
        for bad_id in ["", "   ", "non_existent_preset_9999", "../../etc/passwd", "\0nullbyte"]:
            dna = iv.extraer_adn_estilo(ruta_lamina=None, preset_id=bad_id)
            assert_style_dna_contract(self, dna, f"bad preset id: {repr(bad_id)}")

    def test_corrupt_images_with_preset_fallback(self):
        """Corrupt or zero-byte images with a valid preset fallback must return compliant DNA."""
        for bad_img in [self.corrupt_img, self.zero_byte_img, self.emergency_img]:
            dna = iv.extraer_adn_estilo(ruta_lamina=bad_img, preset_id="pr1a0eef81dc7")
            assert_style_dna_contract(self, dna, f"bad image {bad_img} with valid preset")

    def test_corrupt_images_without_preset_raise_value_error(self):
        """Corrupt or zero-byte images without preset fallback must raise ValueError."""
        for bad_img in [self.corrupt_img, self.zero_byte_img, self.emergency_img]:
            with self.assertRaises(ValueError, msg=f"Should raise ValueError on {bad_img}"):
                iv.extraer_adn_estilo(ruta_lamina=bad_img, preset_id=None)

    @patch("pasos.gemini_cliente.ejecutar")
    @patch("pasos.gemini_cliente.hay_gemini", return_value=True)
    def test_gemini_vision_adversarial_payloads(self, mock_hay, mock_ejecutar):
        """Ensure all adversarial outputs from Gemini Vision yield strictly compliant Style DNA."""
        adversarial_responses = [
            # 1. Partial dict missing most keys
            json.dumps({"medium": "watercolor on cold-press paper"}),
            # 2. Markdown wrapped
            "```json\n" + json.dumps({"medium": "vector line art", "palette_hex": ["#000000", "#FFFFFF"]}) + "\n```",
            # 3. Dirty hex codes (missing #, non-hex characters, integers, None)
            json.dumps({
                "medium": "digital ink",
                "palette_hex": ["123456", "#GGGGGG", 9999, None, "#ABCDEF", "#001122"]
            }),
            # 4. Empty strings for all keys
            json.dumps({k: "" for k in REQUIRED_STYLE_KEYS}),
            # 5. None for all keys
            json.dumps({k: None for k in REQUIRED_STYLE_KEYS}),
            # 6. Completely empty json object
            "{}",
            # 7. Conversational response with no JSON
            "I am unable to parse this image because it contains abstract patterns.",
            # 8. Spanish conversational text embedded in dna_block
            json.dumps({
                "medium": "vector",
                "palette_hex": ["#112233"],
                "dna_block": "2D vector, colors muted, estilo plano de animacion"
            })
        ]

        for idx, payload in enumerate(adversarial_responses):
            mock_ejecutar.return_value = (payload, {})
            # Use unique image to prevent cache hit
            u_img = os.path.join(self.tmp_dir, f"adv_img_{idx}.png")
            im = Image.new("RGB", (200, 200), (100 + idx * 10, 50 + idx * 5, 20 + idx * 8))
            im.save(u_img, format="PNG")

            dna = iv.extraer_adn_estilo(u_img)
            assert_style_dna_contract(self, dna, f"adversarial payload #{idx}")


class TestEmpiricalCharacterAnchorsBoundaries(unittest.TestCase):
    """Rigorous verification of Character Anchors boundaries and schema invariants."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="challenger_char_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(os.path.join(self.banco_dir, "dna"), exist_ok=True)
        self._orig_banco = iv.BANCO
        iv.BANCO = self.banco_dir

        self.valid_char_img = os.path.join(self.tmp_dir, "char.png")
        im = Image.new("RGB", (128, 128), (180, 150, 120))
        d = ImageDraw.Draw(im)
        d.ellipse([(20, 20), (100, 100)], fill=(80, 50, 30))
        im.save(self.valid_char_img, format="PNG")

        self.emergency_char_img = os.path.join(self.tmp_dir, "emergency_char.png")
        im_em = Image.new("RGBA", (100, 100), (20, 25, 35, 255))
        d_em = ImageDraw.Draw(im_em)
        d_em.rectangle([(24, 24), (76, 76)], outline=(212, 175, 55, 120), width=2)
        im_em.save(self.emergency_char_img, format="PNG")

    def tearDown(self):
        iv.BANCO = self._orig_banco
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_name_argument_boundary_values(self):
        """Boundary inputs for nombre_personaje (None, empty, whitespace, numbers)."""
        boundary_names = [None, "", "   ", 12345, "Elena", "Marcus", "Detective Vance"]
        for name in boundary_names:
            anchors = iv.extraer_anclas_personaje(ruta_personaje=None, nombre_personaje=name)
            assert_character_anchors_contract(self, anchors, f"name={repr(name)}")
            if name in (None, "", "   "):
                self.assertEqual(anchors["name"], "character")

    def test_fallback_description_boundary_types(self):
        """descripcion_fallback with None, numbers, lists, or empty string must not crash."""
        for fb in [None, 123, ["tweed coat"], "", "   ", "elderly botanist in green apron"]:
            anchors = iv.extraer_anclas_personaje(
                ruta_personaje=None,
                nombre_personaje="Professor",
                descripcion_fallback=fb
            )
            assert_character_anchors_contract(self, anchors, f"descripcion_fallback={repr(fb)}")

    def test_emergency_canvas_does_not_poison_character_anchors(self):
        """Emergency canvas input falls back cleanly without ValueError or gold border pollution."""
        anchors = iv.extraer_anclas_personaje(self.emergency_char_img, "Captain")
        assert_character_anchors_contract(self, anchors, "emergency canvas fallback")
        self.assertNotIn("212", anchors["anchors_block"])
        self.assertNotIn("emergency", anchors["anchors_block"].lower())
        self.assertNotIn("lienzo", anchors["anchors_block"].lower())

    def test_corrupt_character_image_raises_value_error(self):
        """0-byte and corrupted character sheets raise ValueError."""
        zero_p = os.path.join(self.tmp_dir, "zero.png")
        with open(zero_p, "wb") as f:
            pass
        with self.assertRaises(ValueError):
            iv.extraer_anclas_personaje(zero_p, "Hero")

        corrupt_p = os.path.join(self.tmp_dir, "corrupt.png")
        with open(corrupt_p, "wb") as f:
            f.write(b"NOT_A_PNG" * 20)
        with self.assertRaises(ValueError):
            iv.extraer_anclas_personaje(corrupt_p, "Hero")

    def test_poisoned_character_cache_is_discarded(self):
        """Poisoned character cache file (empty anchors_block) is ignored and healed."""
        huella = iv.huella_fichero(self.valid_char_img)
        cache_path = os.path.join(self.banco_dir, "dna", f"personaje_{huella}.json")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"name": "Poisoned", "anchors_block": ""}, f)

        anchors = iv.extraer_anclas_personaje(self.valid_char_img, "Poisoned")
        assert_character_anchors_contract(self, anchors, "poisoned character cache")
        self.assertTrue(len(anchors["anchors_block"].strip()) > 0)


class TestEmpiricalCacheWriteIntegrity(unittest.TestCase):
    """Rigorous verification that _guardar_cache_huella never writes invalid or corrupt data."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="challenger_cache_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        self.dna_dir = os.path.join(self.banco_dir, "dna")
        os.makedirs(self.dna_dir, exist_ok=True)
        self._orig_banco = iv.BANCO
        iv.BANCO = self.banco_dir

        self.sample_file = os.path.join(self.tmp_dir, "sample.png")
        im = Image.new("RGB", (64, 64), (10, 20, 30))
        im.save(self.sample_file, format="PNG")

    def tearDown(self):
        iv.BANCO = self._orig_banco
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _count_cache_files(self) -> int:
        return len(os.listdir(self.dna_dir))

    def test_guardar_cache_huella_rejects_all_invalid_style_dna(self):
        """_guardar_cache_huella must NEVER write invalid style records."""
        invalid_style_records = [
            None,
            {},
            [],
            "string_instead_of_dict",
            # Missing keys
            {"medium": "vector"},
            # Empty medium
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "medium": ""},
            # Whitespace medium
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "medium": "   "},
            # Non-string medium
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "medium": 123},
            # Empty palette_hex
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "palette_hex": []},
            # Invalid hex code
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "palette_hex": ["#ZZZZZZ"]},
            # Missing # in hex code
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "palette_hex": ["FFFFFF"]},
            # Empty dna_block
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "dna_block": ""},
            # None field
            {**copy.deepcopy(iv.DEFAULT_STYLE_DNA), "lighting_style": None},
        ]

        for idx, bad_record in enumerate(invalid_style_records):
            iv._guardar_cache_huella("estilo", self.sample_file, bad_record)
            self.assertEqual(
                self._count_cache_files(),
                0,
                f"Invalid style record #{idx} was written to cache! Record: {bad_record}"
            )

    def test_guardar_cache_huella_rejects_all_invalid_character_anchors(self):
        """_guardar_cache_huella must NEVER write invalid character records."""
        invalid_char_records = [
            None,
            {},
            [],
            "string",
            {"name": "Elena"},  # missing anchors_block
            {"anchors_block": "abc"},  # missing name
            {"name": "", "anchors_block": "abc"},
            {"name": "   ", "anchors_block": "abc"},
            {"name": "Elena", "anchors_block": ""},
            {"name": "Elena", "anchors_block": "   "},
            {"name": None, "anchors_block": "abc"},
            {"name": "Elena", "anchors_block": None},
            {"name": 123, "anchors_block": "abc"},
            {"name": "Elena", "anchors_block": 456},
        ]

        for idx, bad_record in enumerate(invalid_char_records):
            iv._guardar_cache_huella("personaje", self.sample_file, bad_record)
            self.assertEqual(
                self._count_cache_files(),
                0,
                f"Invalid character record #{idx} was written to cache! Record: {bad_record}"
            )

    def test_guardar_cache_huella_writes_valid_data(self):
        """_guardar_cache_huella writes valid data and produces valid files."""
        # 1. Valid Style DNA
        iv._guardar_cache_huella("estilo", self.sample_file, iv.DEFAULT_STYLE_DNA)
        self.assertEqual(self._count_cache_files(), 1)
        huella = iv.huella_fichero(self.sample_file)
        written_style_path = os.path.join(self.dna_dir, f"estilo_{huella}.json")
        self.assertTrue(os.path.isfile(written_style_path))
        with open(written_style_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert_style_dna_contract(self, data, "persisted style cache file")

        # 2. Valid Character Anchors
        valid_char = {"name": "Elena", "anchors_block": "neat auburn bun, dark green tweed blazer"}
        iv._guardar_cache_huella("personaje", self.sample_file, valid_char)
        self.assertEqual(self._count_cache_files(), 2)
        written_char_path = os.path.join(self.dna_dir, f"personaje_{huella}.json")
        self.assertTrue(os.path.isfile(written_char_path))
        with open(written_char_path, "r", encoding="utf-8") as f:
            c_data = json.load(f)
        assert_character_anchors_contract(self, c_data, "persisted character cache file")


class TestEmpiricalCacheConcurrencyAndAtomicity(unittest.TestCase):
    """Stress test concurrent multi-threaded execution and atomic write safety."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="challenger_concurrency_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(os.path.join(self.banco_dir, "dna"), exist_ok=True)
        self._orig_banco = iv.BANCO
        iv.BANCO = self.banco_dir

    def tearDown(self):
        iv.BANCO = self._orig_banco
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_concurrent_writers_same_file_atomic(self):
        """30 concurrent threads calling _guardar_cache_huella simultaneously on same file."""
        img_path = os.path.join(self.tmp_dir, "shared.png")
        im = Image.new("RGB", (64, 64), (50, 100, 150))
        im.save(img_path, format="PNG")

        def _worker(thread_id):
            dna = copy.deepcopy(iv.DEFAULT_STYLE_DNA)
            dna["medium"] = f"2D vector thread {thread_id}"
            iv._guardar_cache_huella("estilo", img_path, dna)
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(_worker, i) for i in range(30)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 30)

        # File on disk must be completely valid JSON and pass schema invariants
        huella = iv.huella_fichero(img_path)
        cache_path = os.path.join(self.banco_dir, "dna", f"estilo_{huella}.json")
        self.assertTrue(os.path.isfile(cache_path))
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert_style_dna_contract(self, data, "concurrent writes result")

    def test_concurrent_readers_and_writers_interleaved(self):
        """Simultaneous concurrent reads and writes must never encounter corrupted/partial files."""
        img_path = os.path.join(self.tmp_dir, "interleaved.png")
        im = Image.new("RGB", (64, 64), (200, 100, 50))
        im.save(img_path, format="PNG")

        # Seed valid cache
        iv._guardar_cache_huella("estilo", img_path, iv.DEFAULT_STYLE_DNA)

        def _reader(idx):
            dna = iv.extraer_adn_estilo(img_path)
            assert_style_dna_contract(self, dna, f"concurrent read #{idx}")
            return True

        def _writer(idx):
            dna = copy.deepcopy(iv.DEFAULT_STYLE_DNA)
            dna["dna_block"] = f"style descriptor update #{idx}"
            iv._guardar_cache_huella("estilo", img_path, dna)
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(40):
                if i % 2 == 0:
                    futures.append(executor.submit(_writer, i))
                else:
                    futures.append(executor.submit(_reader, i))
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 40)


if __name__ == "__main__":
    unittest.main()
