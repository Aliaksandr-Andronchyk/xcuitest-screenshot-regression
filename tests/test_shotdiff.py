"""Tests for the comparison core. Run: python3 -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from shotdiff import config, demo, png, report, runner  # noqa: E402
from shotdiff.compare import Policy, Region, compare_files, compare_images  # noqa: E402


class PngRoundTrip(unittest.TestCase):
    def test_write_then_read_keeps_pixels(self):
        image = png.Image.blank(7, 5, (10, 20, 30, 255))
        image.set_pixel(3, 2, (250, 1, 99, 128))
        restored = png.read(png.write(image))
        self.assertEqual(restored.size, (7, 5))
        self.assertEqual(restored.pixel(3, 2), (250, 1, 99, 128))
        self.assertEqual(restored.pixels, image.pixels)

    def test_rejects_garbage(self):
        with self.assertRaises(png.PngError):
            png.read(b"definitely not a png")


class Comparison(unittest.TestCase):
    def _pair(self):
        base = png.Image.blank(10, 10, (255, 255, 255, 255))
        return base, base.copy()

    def test_identical_images_have_no_diff(self):
        base, actual = self._pair()
        (changed, counted, ratio, bounds), _ = compare_images(base, actual, Policy())
        self.assertEqual((changed, counted, ratio, bounds), (0, 100, 0.0, None))

    def test_counts_changed_pixels_and_bounds(self):
        base, actual = self._pair()
        actual.set_pixel(4, 6, (0, 0, 0, 255))
        actual.set_pixel(5, 7, (0, 0, 0, 255))
        (changed, _, ratio, bounds), _ = compare_images(base, actual, Policy())
        self.assertEqual(changed, 2)
        self.assertAlmostEqual(ratio, 0.02)
        self.assertEqual(bounds, (4, 6, 5, 7))

    def test_channel_tolerance_absorbs_small_noise(self):
        base, actual = self._pair()
        actual.set_pixel(1, 1, (253, 255, 255, 255))
        strict, _ = compare_images(base, actual, Policy())
        lenient, _ = compare_images(base, actual, Policy(channel_tolerance=2))
        self.assertEqual(strict[0], 1)
        self.assertEqual(lenient[0], 0)

    def test_ignored_region_is_not_counted(self):
        base, actual = self._pair()
        actual.set_pixel(0, 0, (0, 0, 0, 255))
        policy = Policy(ignore=(Region(0, 0, 10, 1),))
        (changed, counted, _, _), _ = compare_images(base, actual, policy)
        self.assertEqual(changed, 0)
        self.assertEqual(counted, 90)

    def test_size_change_is_an_error(self):
        base = png.Image.blank(10, 10)
        with self.assertRaises(ValueError):
            compare_images(base, png.Image.blank(10, 11), Policy())

    def test_region_parsing(self):
        self.assertEqual(Region.parse("1,2,3,4"), Region(1, 2, 3, 4))
        self.assertEqual(Region.parse("1 2 3 4"), Region(1, 2, 3, 4))
        with self.assertRaises(ValueError):
            Region.parse("1,2,3")


class Files(unittest.TestCase):
    def test_diff_image_written_only_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            base, actual = png.Image.blank(4, 4, (255,) * 4), png.Image.blank(4, 4, (255,) * 4)
            png.save(base, tmp / "b.png")
            png.save(actual, tmp / "a.png")
            ok = compare_files("x", tmp / "b.png", tmp / "a.png", tmp / "d.png", Policy())
            self.assertTrue(ok.ok)
            self.assertFalse((tmp / "d.png").exists())

            actual.set_pixel(0, 0, (0, 0, 0, 255))
            png.save(actual, tmp / "a.png")
            bad = compare_files("x", tmp / "b.png", tmp / "a.png", tmp / "d.png", Policy())
            self.assertEqual(bad.status, "failed")
            self.assertTrue((tmp / "d.png").exists())

    def test_size_mismatch_reports_both_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            png.save(png.Image.blank(4, 4), tmp / "b.png")
            png.save(png.Image.blank(4, 5), tmp / "a.png")
            result = compare_files("x", tmp / "b.png", tmp / "a.png", tmp / "d.png", Policy())
            self.assertEqual(result.status, "failed")
            self.assertIn("4x4", result.message)
            self.assertIn("4x5", result.message)


class RunnerAndReport(unittest.TestCase):
    def _suite_dirs(self, tmp):
        baseline, actual = tmp / "base", tmp / "act"
        baseline.mkdir()
        actual.mkdir()
        png.save(png.Image.blank(4, 4, (1, 2, 3, 255)), baseline / "same.png")
        png.save(png.Image.blank(4, 4, (1, 2, 3, 255)), actual / "same.png")
        png.save(png.Image.blank(4, 4, (1, 2, 3, 255)), baseline / "gone.png")
        png.save(png.Image.blank(4, 4, (9, 9, 9, 255)), actual / "fresh.png")
        return baseline, actual

    def test_statuses_cover_new_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            baseline, actual = self._suite_dirs(tmp)
            results = runner.run(baseline, actual, tmp / "diff", config.SuiteConfig())
            statuses = {r.name: r.status for r in results}
            self.assertEqual(statuses, {"same": "passed", "gone": "missing", "fresh": "new"})
            self.assertEqual(runner.exit_code(results), 1)

    def test_accept_promotes_shots(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            baseline, actual = self._suite_dirs(tmp)
            accepted = runner.accept(actual, baseline)
            self.assertEqual(sorted(accepted), ["fresh", "same"])
            after = runner.run(baseline, actual, tmp / "diff", config.SuiteConfig())
            self.assertEqual({r.status for r in after} - {"missing"}, {"passed"})

    def test_report_embeds_images_and_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            baseline, actual = self._suite_dirs(tmp)
            results = runner.run(baseline, actual, tmp / "diff", config.SuiteConfig())
            html_path, json_path = runner.publish(results, tmp / "out")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("data:image/png;base64,", html)
            self.assertIn("нет в прогоне", html)
            self.assertIn("fresh", html)
            self.assertTrue(json_path.exists())
            self.assertIn('"status": "missing"', json_path.read_text(encoding="utf-8"))

    def test_report_survives_empty_run(self):
        self.assertIn("снимков нет", report.render([]))


class Config(unittest.TestCase):
    def test_missing_file_gives_defaults(self):
        suite = config.load("/nonexistent/shotdiff.json")
        self.assertEqual(suite.policy_for("anything"), Policy())

    def test_per_shot_overrides_inherit_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text(
                '{"channel_tolerance": 3, "ignore": ["0,0,5,5"], '
                '"shots": {"paywall": {"max_diff_ratio": 0.5}}}',
                encoding="utf-8",
            )
            suite = config.load(path)
            paywall = suite.policy_for("paywall")
            self.assertEqual(paywall.channel_tolerance, 3)
            self.assertEqual(paywall.max_diff_ratio, 0.5)
            self.assertEqual(paywall.ignore, (Region(0, 0, 5, 5),))
            self.assertEqual(suite.policy_for("other").max_diff_ratio, 0.0)


class Demo(unittest.TestCase):
    def test_demo_catches_planted_regressions_and_ignores_the_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            demo.main(tmp)
            payload = (Path(tmp) / "report" / "report.json").read_text(encoding="utf-8")
            self.assertIn('"name": "settings"', payload)
            results = {r["name"]: r["status"] for r in __import__("json").loads(payload)["shots"]}
            self.assertEqual(results["settings"], "passed")  # only the ticking clock moved
            self.assertEqual(results["feed"], "failed")
            self.assertEqual(results["paywall"], "failed")


if __name__ == "__main__":
    unittest.main()
