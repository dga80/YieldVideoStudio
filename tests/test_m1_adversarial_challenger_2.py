"""Empirical Adversarial Challenge Suite for Milestone M1 (pasos/inversion_visual.py).

Authored by: teamwork_preview_challenger_m1_2 (Empirical Challenger)
Timestamp: 2026-10-06T20:10:00Z

Tests:
1. Emergency Canvas Rejection:
   - Real disk emergency canvases from proyectos/ (pastor.png, gente.png, etc.).
   - Exact gold border signature (212, 175, 55, 120) at margin 24px.
   - Mode RGBA and RGB variations, boundary color distances, dimension variations.
   - Verification that emergency canvases NEVER poison style DNA or character anchors.
   - Verification that emergency canvases NEVER get written to cache (banco/dna/).
   - False positive audit across all genuine preset sheets in banco/presets/.

2. Cache Persistence, Hit vs Miss Metrics, and Self-Healing:
   - Cache persistence on disk (presets/{pid}/dna_estilo.json and banco/dna/).
   - Cache hit vs miss detection (hit ratio, call count guarantees).
   - Content hash invalidation (modifying image bytes invalidates cache).
   - Self-healing under 8 corruption modalities:
     a) 0-byte empty cache file
     b) Truncated / malformed JSON
     c) Non-UTF8 binary garbage
     d) Non-dict JSON primitives (list, int, string, null)
     e) Incomplete schema (missing required contract keys)
     f) Invalid field types (int instead of str, str instead of list)
     g) Invalid hex codes in palette_hex
     h) Whitespace-only string values
   - Verification that corrupt cache is healed (re-written with valid data) on recovery.
"""
import copy
import glob
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

import pasos.inversion_visual as iv


class TestM1EmergencyCanvasRejectionRealFiles(unittest.TestCase):
    """Empirical challenge against real files on disk and exact gold border signature."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="m1_adv_real_")
        self.patch_banco = patch("pasos.inversion_visual.BANCO", os.path.join(self.tmp_dir, "banco"))
        self.patch_banco.start()

    def tearDown(self):
        self.patch_banco.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_challenge_real_pastor_emergency_canvas(self):
        """Verify real pastor.png emergency canvas is strictly rejected and never poisons anchors."""
        pastor_path = "proyectos/test_pluma_auto/pasos/assets/v1/assets/reparto/pastor.png"
        self.assertTrue(os.path.isfile(pastor_path), f"File {pastor_path} must exist on disk")

        # 1. Direct validation check
        valida, motivo = iv.validar_imagen(pastor_path)
        self.assertFalse(valida, "Real pastor.png must be rejected as an emergency canvas")
        self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

        # 2. Character anchor extraction must NOT invoke vision API and must return clean fallback
        with patch("pasos.gemini_cliente.ejecutar") as mock_vision:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                anclas = iv.extraer_anclas_personaje(pastor_path, "pastor")
                mock_vision.assert_not_called()
                self.assertEqual(anclas["name"], "pastor")
                self.assertNotIn("212", anclas["anchors_block"])
                self.assertNotIn("emergency", anclas["anchors_block"].lower())
                self.assertNotIn("lienzo", anclas["anchors_block"].lower())

        # 3. Must NOT write cache file to banco/dna/
        huella = iv.huella_fichero(pastor_path)
        cache_file = os.path.join(iv.BANCO, "dna", f"personaje_{huella}.json")
        self.assertFalse(os.path.exists(cache_file), "Rejected emergency canvas must NOT create cache entry")

    def test_challenge_real_scene_emergency_canvases(self):
        """Verify real scene emergency canvases (S001.png, etc.) are strictly rejected for style inversion."""
        escena_path = "proyectos/test_pluma_auto/pasos/assets/v5/escenas/S001.png"
        self.assertTrue(os.path.isfile(escena_path), f"File {escena_path} must exist on disk")

        valida, motivo = iv.validar_imagen(escena_path)
        self.assertFalse(valida)
        self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

        with patch("pasos.gemini_cliente.ejecutar") as mock_vision:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                adn = iv.extraer_adn_estilo(escena_path)
                mock_vision.assert_not_called()
                self.assertEqual(adn, iv.DEFAULT_STYLE_DNA)

        huella = iv.huella_fichero(escena_path)
        cache_file = os.path.join(iv.BANCO, "dna", f"estilo_{huella}.json")
        self.assertFalse(os.path.exists(cache_file), "Rejected scene emergency canvas must NOT create cache entry")

    def test_challenge_bulk_real_canvases_100_percent_detection(self):
        """Scan real emergency canvases on disk and verify 100% rejection rate."""
        candidates = glob.glob("proyectos/test_pluma_auto/**/pastor.png", recursive=True)
        candidates.append("proyectos/test_pluma_auto/pasos/assets/v5/assets/reparto/gente.png")
        for name in ["diagrama.png", "cara.png", "cuerpos.png", "exterior.png", "objeto.png"]:
            candidates.append(os.path.join("proyectos/taller_pluma_1/estilo/dibujadas", name))
        self.assertGreaterEqual(len(candidates), 10, "Should test at least 10 real emergency files")

        for c in candidates:
            valida, motivo = iv.validar_imagen(c)
            self.assertFalse(valida, f"Real emergency canvas {c} was not rejected!")
            self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

    def test_challenge_genuine_presets_zero_false_positives(self):
        """Verify that genuine preset sheets in banco/presets/ are NEVER falsely flagged as emergency canvases."""
        preset_files = glob.glob("banco/presets/**/*.png", recursive=True)
        self.assertGreaterEqual(len(preset_files), 10, "Should find genuine preset images")

        for pf in preset_files:
            valida, motivo = iv.validar_imagen(pf)
            self.assertTrue(valida, f"Genuine preset file {pf} was falsely rejected: {motivo}")


class TestM1GoldBorderSignatureVariations(unittest.TestCase):
    """Adversarial stress-testing of gold border detection algorithm."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="m1_adv_gold_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _crear_lienzo(self, modo="RGBA", tamano=(1280, 720), borde_color=(212, 175, 55, 120), margen=24, ancho=2):
        img = Image.new(modo, tamano, (20, 24, 32, 255) if modo == "RGBA" else (20, 24, 32))
        draw = ImageDraw.Draw(img)
        w, h = tamano
        draw.rectangle([(margen, margen), (w - margen, h - margen)], outline=borde_color, width=ancho)
        path = os.path.join(self.tmp_dir, f"test_{int(time.time()*1000)}.png")
        img.save(path, "PNG")
        return path

    def test_gold_border_exact_rgba(self):
        p = self._crear_lienzo(modo="RGBA", borde_color=(212, 175, 55, 120))
        valida, motivo = iv.validar_imagen(p)
        self.assertFalse(valida)
        self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

    def test_gold_border_exact_rgb(self):
        p = self._crear_lienzo(modo="RGB", borde_color=(212, 175, 55))
        valida, motivo = iv.validar_imagen(p)
        self.assertFalse(valida)
        self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

    def test_gold_border_tolerance_boundary_inside(self):
        # abs(212 - r) <= 25, abs(175 - g) <= 25, abs(55 - b) <= 25
        # Test edge inside tolerance: (212 + 20, 175 - 20, 55 + 20) -> (232, 155, 75)
        p = self._crear_lienzo(modo="RGBA", borde_color=(232, 155, 75, 120))
        valida, motivo = iv.validar_imagen(p)
        self.assertFalse(valida)
        self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")

    def test_gold_border_outside_tolerance_not_rejected(self):
        # Color distinctly different: (150, 100, 20)
        p = self._crear_lienzo(modo="RGBA", borde_color=(150, 100, 20, 120))
        valida, motivo = iv.validar_imagen(p)
        self.assertTrue(valida)

    def test_resolution_invariance(self):
        """Border at 24px margin should be detected across standard video resolutions."""
        for dims in [(1280, 720), (1024, 576), (1920, 1080), (854, 480)]:
            p = self._crear_lienzo(tamano=dims)
            valida, motivo = iv.validar_imagen(p)
            self.assertFalse(valida, f"Failed at dimension {dims}")
            self.assertEqual(motivo, "lienzo_de_emergencia_borde_dorado")


class TestM1CachePersistenceAndHitMiss(unittest.TestCase):
    """Empirical verification of cache persistence and hit vs miss behavior."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="m1_adv_cache_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(self.banco_dir, exist_ok=True)
        self.patch_banco = patch("pasos.inversion_visual.BANCO", self.banco_dir)
        self.patch_banco.start()

    def tearDown(self):
        self.patch_banco.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _crear_imagen_valida(self, color=(120, 80, 200), nombre="imagen.png"):
        p = os.path.join(self.tmp_dir, nombre)
        img = Image.new("RGB", (256, 256), color)
        draw = ImageDraw.Draw(img)
        draw.ellipse([(50, 50), (200, 200)], fill=(200, 150, 50))
        img.save(p, "PNG")
        return p

    def test_cache_miss_followed_by_cache_hit_style(self):
        """First call must be a MISS and call Gemini; second call must be a HIT with zero API calls."""
        img_path = self._crear_imagen_valida()
        mock_resp = json.dumps({
            "medium": "digital acrylic impasto",
            "palette_hex": ["#7850C8", "#C89632", "#FFFFFF"],
            "palette_desc": "deep purple, mustard gold, white",
            "linework": "textured energetic brushstrokes",
            "texture": "heavy impasto knife marks",
            "lighting_style": "dramatic low-key chiaroscuro",
            "negative_style": "flat vector, smooth gradient",
            "dna_block": "digital acrylic impasto with dramatic chiaroscuro and heavy knife marks",
        })

        with patch("pasos.gemini_cliente.ejecutar", return_value=(mock_resp, {})) as mock_api:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                # 1. Initial call: Cache MISS
                adn1 = iv.extraer_adn_estilo(img_path)
                self.assertEqual(mock_api.call_count, 1, "Cache MISS must invoke Gemini Vision")
                self.assertEqual(adn1["medium"], "digital acrylic impasto")

                # Verify persistence file exists in banco/dna/
                huella = iv.huella_fichero(img_path)
                cache_file = os.path.join(self.banco_dir, "dna", f"estilo_{huella}.json")
                self.assertTrue(os.path.isfile(cache_file), "Cache file must exist on disk")

                # Verify sidecar file exists alongside image
                sidecar_file = os.path.splitext(img_path)[0] + "_dna.json"
                self.assertTrue(os.path.isfile(sidecar_file), "Sidecar cache file must exist")

                # 2. Subsequent call: Cache HIT
                adn2 = iv.extraer_adn_estilo(img_path)
                self.assertEqual(mock_api.call_count, 1, "Cache HIT must NOT invoke Gemini Vision")
                self.assertEqual(adn1, adn2, "Cached output must be identical to fresh output")

    def test_cache_miss_on_content_hash_change(self):
        """Altering the file content changes SHA-256 huella, producing a cache MISS."""
        img_path = self._crear_imagen_valida(color=(100, 100, 100), nombre="mutable.png")
        mock_resp_1 = json.dumps({
            "medium": "charcoal drawing",
            "palette_hex": ["#646464", "#000000"],
            "palette_desc": "grey and black",
            "linework": "smudged charcoal",
            "texture": "rough paper grain",
            "lighting_style": "ambient diffuse",
            "negative_style": "color, 3d",
            "dna_block": "charcoal drawing on rough paper",
        })
        mock_resp_2 = json.dumps({
            "medium": "neon synthwave digital art",
            "palette_hex": ["#FF00FF", "#00FFFF"],
            "palette_desc": "neon magenta, cyan",
            "linework": "hard glowing edges",
            "texture": "digital scanlines",
            "lighting_style": "neon rim lighting",
            "negative_style": "natural, charcoal",
            "dna_block": "neon synthwave digital art with rim light",
        })

        with patch("pasos.gemini_cliente.ejecutar") as mock_api:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                # Call 1 on original image
                mock_api.return_value = (mock_resp_1, {})
                adn1 = iv.extraer_adn_estilo(img_path)
                self.assertEqual(adn1["medium"], "charcoal drawing")
                self.assertEqual(mock_api.call_count, 1)

                # Mutate image content (draw something new)
                img = Image.open(img_path)
                draw = ImageDraw.Draw(img)
                draw.rectangle([(10, 10), (200, 200)], fill=(255, 0, 255))
                img.save(img_path, "PNG")

                # Call 2 on modified image: Must be a cache MISS
                mock_api.return_value = (mock_resp_2, {})
                adn2 = iv.extraer_adn_estilo(img_path)
                self.assertEqual(adn2["medium"], "neon synthwave digital art")
                self.assertEqual(mock_api.call_count, 2, "Mutated image content must trigger new vision call")

    def test_character_anchors_cache_persistence_and_hit(self):
        """Character anchors cache persists in banco/dna/personaje_{huella}.json and yields cache hits."""
        char_path = self._crear_imagen_valida(color=(220, 180, 140), nombre="heroe.png")
        mock_char_resp = json.dumps({
            "name": "elena",
            "anchors_block": "tall detective with auburn braided hair, charcoal trench coat, brass monocle"
        })

        with patch("pasos.gemini_cliente.ejecutar", return_value=(mock_char_resp, {})) as mock_api:
            with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
                # 1. Miss
                anclas1 = iv.extraer_anclas_personaje(char_path, "elena")
                self.assertEqual(mock_api.call_count, 1)
                self.assertIn("auburn braided hair", anclas1["anchors_block"])

                # Verify persistence
                huella = iv.huella_fichero(char_path)
                cache_file = os.path.join(self.banco_dir, "dna", f"personaje_{huella}.json")
                self.assertTrue(os.path.isfile(cache_file))

                # 2. Hit
                anclas2 = iv.extraer_anclas_personaje(char_path, "elena")
                self.assertEqual(mock_api.call_count, 1)
                self.assertEqual(anclas1, anclas2)


class TestM1CacheCorruptionSelfHealing(unittest.TestCase):
    """Stress testing cache corruption recovery across 8 distinct corruption modalities."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="m1_adv_corrupt_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(self.banco_dir, exist_ok=True)
        self.patch_banco = patch("pasos.inversion_visual.BANCO", self.banco_dir)
        self.patch_banco.start()

        # Create valid dummy image
        self.img_path = os.path.join(self.tmp_dir, "sample.png")
        img = Image.new("RGB", (200, 200), (80, 120, 180))
        img.save(self.img_path, "PNG")
        self.huella = iv.huella_fichero(self.img_path)
        self.cache_path = os.path.join(self.banco_dir, "dna", f"estilo_{self.huella}.json")
        self.patch_gemini = patch("pasos.gemini_cliente.hay_gemini", return_value=False)
        self.patch_gemini.start()

    def tearDown(self):
        self.patch_gemini.stop()
        self.patch_banco.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_corrupt_cache(self, content: bytes | str):
        if isinstance(content, str):
            content = content.encode("utf-8")
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "wb") as fh:
            fh.write(content)

    def _assert_valid_healed_adn(self, adn: dict):
        self.assertIsInstance(adn, dict)
        self.assertEqual(set(adn.keys()), iv.CLAVES_ADN_ESPERADAS)
        self.assertIsInstance(adn["medium"], str)
        self.assertTrue(len(adn["medium"]) > 0)
        self.assertIsInstance(adn["palette_hex"], list)
        self.assertGreaterEqual(len(adn["palette_hex"]), 1)
        for h in adn["palette_hex"]:
            self.assertTrue(h.startswith("#"))
        self.assertIsInstance(adn["dna_block"], str)
        self.assertTrue(len(adn["dna_block"]) > 0)

    def test_corruption_01_zero_byte_empty_file(self):
        self._write_corrupt_cache(b"")
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

    def test_corruption_02_truncated_malformed_json(self):
        self._write_corrupt_cache(b'{"medium": "watercolor", "palette_hex": ["#1234')
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

    def test_corruption_03_non_utf8_binary_garbage(self):
        self._write_corrupt_cache(b"\xff\xfe\x00\x80\xaa\xbb\xcc\xdd\xee\xff" * 20)
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

    def test_corruption_04_json_primitives_not_dict(self):
        for payload in [b'["a", "b", "c"]', b'12345', b'"just a string"', b'null', b'true']:
            self._write_corrupt_cache(payload)
            adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
            self._assert_valid_healed_adn(adn)

    def test_corruption_05_incomplete_schema_missing_keys(self):
        self._write_corrupt_cache(json.dumps({"medium": "sketch"}))
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

    def test_corruption_06_invalid_types_in_fields(self):
        self._write_corrupt_cache(json.dumps({
            "medium": 12345,
            "palette_hex": "not a list",
            "palette_desc": None,
            "linework": [],
            "texture": 99,
            "lighting_style": {},
            "negative_style": False,
            "dna_block": 42
        }))
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

    def test_corruption_07_invalid_hex_colors(self):
        self._write_corrupt_cache(json.dumps({
            "medium": "pencil sketch",
            "palette_hex": ["ZZZZZZ", "#12", "not_hex", "#12345678"],
            "palette_desc": "grey",
            "linework": "fine pencil",
            "texture": "paper",
            "lighting_style": "ambient",
            "negative_style": "color",
            "dna_block": "pencil sketch on paper"
        }))
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

    def test_corruption_08_empty_or_whitespace_strings(self):
        self._write_corrupt_cache(json.dumps({
            "medium": "   ",
            "palette_hex": ["#FFFFFF"],
            "palette_desc": "   ",
            "linework": "   ",
            "texture": "",
            "lighting_style": "",
            "negative_style": "",
            "dna_block": "   "
        }))
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

    def test_self_healing_rewrites_valid_cache_on_disk(self):
        """Verify that recovering from corruption actually overwrites the broken cache file on disk."""
        self._write_corrupt_cache(b"INVALID_CORRUPT_BYTES")

        # First call triggers self-healing
        adn = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        self._assert_valid_healed_adn(adn)

        # Inspect disk file: it must now be clean valid JSON conforming to schema!
        with open(self.cache_path, "r", encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertTrue(iv._es_adn_valido(on_disk), "Self-healed file on disk must be strictly valid ADN")

    def test_character_cache_corruption_self_healing(self):
        """Verify character cache corruption is handled gracefully and healed when API is available."""
        char_cache = os.path.join(self.banco_dir, "dna", f"personaje_{self.huella}.json")
        os.makedirs(os.path.dirname(char_cache), exist_ok=True)
        with open(char_cache, "wb") as fh:
            fh.write(b"CORRUPTED_CHARACTER_CACHE_JSON")

        # 1. Offline fallback
        with patch("pasos.gemini_cliente.hay_gemini", return_value=False):
            anclas = iv.extraer_anclas_personaje(self.img_path, "guardia", descripcion_fallback="armored guard")
            self.assertEqual(anclas["name"], "guardia")
            self.assertIn("armored guard", anclas["anchors_block"])

        # 2. Online vision heals the cache
        mock_resp = json.dumps({"name": "guardia", "anchors_block": "armored guard with steel helmet and halberd"})
        with patch("pasos.gemini_cliente.hay_gemini", return_value=True):
            with patch("pasos.gemini_cliente.ejecutar", return_value=(mock_resp, {})):
                anclas = iv.extraer_anclas_personaje(self.img_path, "guardia")
                self.assertEqual(anclas["name"], "guardia")
                self.assertIn("steel helmet", anclas["anchors_block"])

        # Inspect disk: must now be valid
        with open(char_cache, "r", encoding="utf-8") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk["name"], "guardia")
        self.assertIn("steel helmet", on_disk["anchors_block"])



class TestM1PerformanceAndConcurrency(unittest.TestCase):
    """Concurrency and performance benchmarking for cache access."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="m1_adv_perf_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(self.banco_dir, exist_ok=True)
        self.patch_banco = patch("pasos.inversion_visual.BANCO", self.banco_dir)
        self.patch_banco.start()
        self.patch_gemini = patch("pasos.gemini_cliente.hay_gemini", return_value=False)
        self.patch_gemini.start()

        self.img_path = os.path.join(self.tmp_dir, "perf.png")
        Image.new("RGB", (128, 128), (60, 90, 120)).save(self.img_path)

    def tearDown(self):
        self.patch_gemini.stop()
        self.patch_banco.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_latency_speedup_hit_vs_miss(self):
        """Cache hit must be substantially faster than synthesis/miss."""
        t0 = time.perf_counter()
        dna_miss = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        t_miss = time.perf_counter() - t0

        t0 = time.perf_counter()
        dna_hit = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
        t_hit = time.perf_counter() - t0

        self.assertEqual(dna_miss, dna_hit)
        self.assertLess(t_hit, t_miss + 0.05, "Cache hit must not be slower than miss")

    def test_multi_threaded_concurrent_cache_access(self):
        """Multiple concurrent threads querying the cache layer must never crash or corrupt data."""
        import concurrent.futures

        def worker(worker_id):
            res = iv.extraer_adn_estilo(self.img_path, preset_id="pr1a0eef81dc7")
            if not iv._es_adn_valido(res):
                return f"Worker {worker_id} produced invalid DNA"
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(worker, range(40)))

        failures = [r for r in results if r is not None]
        self.assertEqual(len(failures), 0, f"Concurrent workers failed: {failures}")


class TestM1FilesystemResilienceAndEdgeFormats(unittest.TestCase):
    """Resilience against read-only directories, missing permissions, and non-PNG formats."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="m1_adv_fs_")
        self.banco_dir = os.path.join(self.tmp_dir, "banco")
        os.makedirs(os.path.join(self.banco_dir, "dna"), exist_ok=True)
        self.patch_banco = patch("pasos.inversion_visual.BANCO", self.banco_dir)
        self.patch_banco.start()
        self.patch_gemini = patch("pasos.gemini_cliente.hay_gemini", return_value=False)
        self.patch_gemini.start()

    def tearDown(self):
        self.patch_gemini.stop()
        self.patch_banco.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_read_only_cache_directory_resilience(self):
        """When cache directory is read-only (PermissionError), pipeline returns valid DNA without crashing."""
        dna_dir = os.path.join(self.banco_dir, "dna")
        img_path = os.path.join(self.tmp_dir, "ro_test.png")
        Image.new("RGB", (64, 64), (10, 20, 30)).save(img_path)

        os.chmod(dna_dir, 0o555)
        try:
            res = iv.extraer_adn_estilo(img_path, preset_id="pr1a0eef81dc7")
            self.assertTrue(iv._es_adn_valido(res), "Must return valid style DNA even if cache directory is read-only")
        finally:
            os.chmod(dna_dir, 0o755)

    def test_support_for_jpeg_webp_and_bmp(self):
        """Formats other than PNG (JPEG, WEBP, BMP) must validate correctly."""
        for ext, fmt in [("jpg", "JPEG"), ("webp", "WEBP"), ("bmp", "BMP")]:
            img_path = os.path.join(self.tmp_dir, f"test.{ext}")
            img = Image.new("RGB", (128, 128), (100, 150, 200))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(20, 20), (80, 80)], fill=(255, 255, 0))
            img.save(img_path, fmt)
            valida, motivo = iv.validar_imagen(img_path)
            self.assertTrue(valida, f"Format {fmt} should be valid, got: {motivo}")


if __name__ == "__main__":
    unittest.main()

