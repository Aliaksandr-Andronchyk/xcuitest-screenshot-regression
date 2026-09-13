"""Synthetic run, so the pipeline can be seen working without a Mac.

Draws three fake app screens as baselines, then draws them again with the
kind of change a real regression looks like: a shifted button, a recoloured
badge, a clock that ticks inside an ignored region. Then compares and reports.
"""

from __future__ import annotations

from pathlib import Path

from . import png, runner
from .compare import Policy, Region
from .config import SuiteConfig

WIDTH, HEIGHT = 240, 480
STATUS_BAR = Region(0, 0, WIDTH, 28)


def _fill(img, region, color):
    for y in range(max(0, region.y), min(img.height, region.y + region.height)):
        for x in range(max(0, region.x), min(img.width, region.x + region.width)):
            img.set_pixel(x, y, color)


def _screen(background):
    img = png.Image.blank(WIDTH, HEIGHT, background + (255,))
    _fill(img, STATUS_BAR, (28, 28, 32, 255))
    return img


def _clock(img, ticks):
    """A few pixels in the status bar that change every run, on purpose."""
    for i in range(6):
        x = 200 + i
        img.set_pixel(x, 12 + (ticks + i) % 6, (255, 255, 255, 255))


def draw_feed(shifted=False, ticks=0):
    img = _screen((246, 246, 248))
    for row in range(5):
        y = 60 + row * 70
        _fill(img, Region(16, y, WIDTH - 32, 56), (255, 255, 255, 255))
        _fill(img, Region(28, y + 14, 90, 10), (60, 60, 68, 255))
        _fill(img, Region(28, y + 32, 140, 8), (170, 170, 180, 255))
    _clock(img, ticks)
    if shifted:
        _fill(img, Region(28, 74, 90, 10), (246, 246, 248, 255))
        _fill(img, Region(34, 74, 90, 10), (60, 60, 68, 255))
    return img


def draw_paywall(recolored=False, ticks=0):
    img = _screen((18, 18, 24))
    _fill(img, Region(24, 80, WIDTH - 48, 120), (38, 38, 48, 255))
    badge = (255, 92, 40, 255) if not recolored else (40, 190, 120, 255)
    _fill(img, Region(24, 230, WIDTH - 48, 44), badge)
    _fill(img, Region(60, 300, WIDTH - 120, 10), (120, 120, 140, 255))
    _clock(img, ticks)
    return img


def draw_settings(ticks=0):
    img = _screen((255, 255, 255))
    for row in range(7):
        y = 50 + row * 44
        _fill(img, Region(0, y, WIDTH, 1), (225, 225, 230, 255))
        _fill(img, Region(20, y + 16, 110, 9), (50, 50, 58, 255))
    _clock(img, ticks)
    return img


def main(out_dir) -> int:
    out = Path(out_dir)
    baseline_dir, actual_dir = out / "Baselines", out / "actual"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    actual_dir.mkdir(parents=True, exist_ok=True)

    png.save(draw_feed(ticks=0), baseline_dir / "feed.png")
    png.save(draw_paywall(ticks=0), baseline_dir / "paywall.png")
    png.save(draw_settings(ticks=0), baseline_dir / "settings.png")

    # the fresh run: feed button moved, paywall badge recoloured, clock ticked
    png.save(draw_feed(shifted=True, ticks=3), actual_dir / "feed.png")
    png.save(draw_paywall(recolored=True, ticks=3), actual_dir / "paywall.png")
    png.save(draw_settings(ticks=3), actual_dir / "settings.png")

    suite = SuiteConfig(default=Policy(channel_tolerance=2, max_diff_ratio=0.0005, ignore=(STATUS_BAR,)))
    results = runner.run(baseline_dir, actual_dir, out / "diff", suite)
    html_path, json_path = runner.publish(results, out / "report", context={"устройство": "демо, без симулятора"})

    for result in results:
        print("  %-9s %-10s %s" % (result.status, result.name, result.message))
    print("отчёт: %s" % html_path)
    print("json:  %s" % json_path)
    return 0
