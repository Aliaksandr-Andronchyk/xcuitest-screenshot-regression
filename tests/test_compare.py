"""Tests for the part that does not need a Mac: PNG, diff, report.

    python3 -m unittest discover -s tests -v
"""

import os
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xcshot import compare, png, report  # noqa: E402


def encode(width, height, rows, color_type=2, filters=None):
    """Build a PNG by hand so the reader can be tested against every filter."""
    channels = 3 if color_type == 2 else 4
    filters = filters or [0] * height
    raw = bytearray()
    prev = bytearray(width * channels)
    for y in range(height):
        line = bytearray(rows[y])
        ft = filters[y]
        encoded = bytearray(len(line))
        for i in range(len(line)):
            left = line[i - channels] if i >= channels else 0
            up = prev[i]
            up_left = prev[i - channels] if i >= channels else 0
            if ft == 0:
                pred = 0
            elif ft == 1:
                pred = left
            elif ft == 2:
                pred = up
            elif ft == 3:
                pred = (left + up) >> 1
            else:
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                pred = left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)
            encoded[i] = (line[i] - pred) & 0xFF
        raw.append(ft)
        raw += encoded
        prev = line

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (png.PNG_MAGIC + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw)))
            + chunk(b"IEND", b""))


class PngTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_round_trip(self):
        image = png.Image.blank(4, 3, (10, 20, 30))
        image.set(2, 1, (200, 100, 50))
        path = self.path("a.png")
        png.write(path, image)
        back = png.read(path)
        self.assertEqual(back.size, (4, 3))
        self.assertEqual(back.get(2, 1), (200, 100, 50))
        self.assertEqual(back.get(0, 0), (10, 20, 30))
        self.assertEqual(back.pixels, image.pixels)

    def test_every_scanline_filter(self):
        width, height = 5, 5
        rows = [
            bytes((x * 7 + y * 13) % 256 for x in range(width * 3))
            for y in range(height)
        ]
        for ft in range(5):
            path = self.path("f%d.png" % ft)
            with open(path, "wb") as fh:
                fh.write(encode(width, height, rows, filters=[ft] * height))
            image = png.read(path)
            self.assertEqual(
                bytes(image.pixels), b"".join(rows), "filter %d decoded wrong" % ft
            )

    def test_alpha_is_dropped(self):
        rows = [bytes([1, 2, 3, 255, 4, 5, 6, 128])]
        path = self.path("rgba.png")
        with open(path, "wb") as fh:
            fh.write(encode(2, 1, rows, color_type=6))
        image = png.read(path)
        self.assertEqual(image.get(0, 0), (1, 2, 3))
        self.assertEqual(image.get(1, 0), (4, 5, 6))

    def test_not_a_png(self):
        path = self.path("nope.png")
        with open(path, "wb") as fh:
            fh.write(b"just text")
        with self.assertRaises(png.PngError):
            png.read(path)


class DiffTest(unittest.TestCase):

    def test_identical_images_have_no_changed_pixels(self):
        a = png.Image.blank(8, 8, (120, 120, 120))
        b = png.Image.blank(8, 8, (120, 120, 120))
        changed, _ = compare.diff_images(a, b)
        self.assertEqual(changed, 0)

    def test_tolerance_absorbs_small_noise(self):
        a = png.Image.blank(4, 4, (100, 100, 100))
        b = png.Image.blank(4, 4, (104, 100, 100))
        self.assertEqual(compare.diff_images(a, b, tolerance=0)[0], 16)
        self.assertEqual(compare.diff_images(a, b, tolerance=3)[0], 16)
        self.assertEqual(compare.diff_images(a, b, tolerance=4)[0], 0)

    def test_diff_image_marks_the_changed_pixel(self):
        a = png.Image.blank(3, 3, (0, 0, 0))
        b = png.Image.blank(3, 3, (0, 0, 0))
        b.set(1, 1, (255, 255, 255))
        changed, diff = compare.diff_images(a, b)
        self.assertEqual(changed, 1)
        self.assertEqual(diff.get(1, 1), compare.DIFF_TINT)
        self.assertNotEqual(diff.get(0, 0), compare.DIFF_TINT)

    def test_size_mismatch_is_an_error(self):
        with self.assertRaises(ValueError):
            compare.diff_images(png.Image.blank(2, 2), png.Image.blank(2, 3))


class RunTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.baseline = os.path.join(self.dir, "baseline")
        self.current = os.path.join(self.dir, "current")
        self.diff = os.path.join(self.dir, "diff")
        os.makedirs(self.baseline)
        os.makedirs(self.current)

    def put(self, folder, name, image):
        png.write(os.path.join(folder, name + ".png"), image)

    def test_statuses_of_a_whole_run(self):
        same = png.Image.blank(10, 10, (30, 30, 30))
        self.put(self.baseline, "01_same", same)
        self.put(self.current, "01_same", same)

        moved = png.Image.blank(10, 10, (30, 30, 30))
        for x in range(10):
            moved.set(x, 5, (255, 255, 255))
        self.put(self.baseline, "02_moved", png.Image.blank(10, 10, (30, 30, 30)))
        self.put(self.current, "02_moved", moved)

        self.put(self.current, "03_brand_new", same)
        self.put(self.baseline, "04_gone", same)

        self.put(self.baseline, "05_resized", png.Image.blank(10, 10))
        self.put(self.current, "05_resized", png.Image.blank(10, 12))

        results = compare.compare_run(self.baseline, self.current, self.diff)
        by_name = {r.name: r for r in results}
        self.assertEqual(by_name["01_same"].status, "pass")
        self.assertEqual(by_name["02_moved"].status, "fail")
        self.assertEqual(by_name["03_brand_new"].status, "new")
        self.assertEqual(by_name["04_gone"].status, "missing")
        self.assertEqual(by_name["05_resized"].status, "fail")
        self.assertIn("size changed", by_name["05_resized"].message)

        self.assertEqual(by_name["02_moved"].changed_pixels, 10)
        self.assertAlmostEqual(by_name["02_moved"].ratio, 0.1)
        self.assertTrue(os.path.exists(by_name["02_moved"].diff_path))
        self.assertIsNone(by_name["01_same"].diff_path)

    def test_threshold_lets_small_changes_pass(self):
        base = png.Image.blank(10, 10, (0, 0, 0))
        changed = png.Image.blank(10, 10, (0, 0, 0))
        changed.set(0, 0, (255, 255, 255))  # 1 of 100 pixels
        self.put(self.baseline, "case", base)
        self.put(self.current, "case", changed)

        strict = compare.compare_run(self.baseline, self.current, self.diff)[0]
        self.assertEqual(strict.status, "fail")

        lenient = compare.compare_run(
            self.baseline, self.current, self.diff, threshold=0.02
        )[0]
        self.assertEqual(lenient.status, "pass")

    def test_report_is_one_standalone_file(self):
        base = png.Image.blank(6, 6, (0, 0, 0))
        other = png.Image.blank(6, 6, (255, 255, 255))
        self.put(self.baseline, "case", base)
        self.put(self.current, "case", other)

        results = compare.compare_run(self.baseline, self.current, self.diff)
        path = report.write(os.path.join(self.dir, "out", "report.html"), results,
                            device="iPhone 15 (17.5)")
        with open(path, encoding="utf-8") as fh:
            html = fh.read()

        self.assertIn("<!doctype html>", html)
        self.assertIn("iPhone 15 (17.5)", html)
        self.assertIn("case", html)
        self.assertEqual(html.count("data:image/png;base64,"), 3)
        self.assertNotIn('src="shots', html)  # nothing loaded from disk

    def test_empty_folders_report_nothing(self):
        self.assertEqual(compare.compare_run(self.baseline, self.current, self.diff), [])


if __name__ == "__main__":
    unittest.main()
