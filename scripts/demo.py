"""Run the whole comparison without a Mac.

Draws four fake phone screens as the baseline, then the same four with the
kind of changes a real run produces: nothing, a shifted button, a colour
change, a new screen. Compares them and opens the report path.

    python3 scripts/demo.py
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xcshot import png  # noqa: E402

W, H = 180, 320
BG = (247, 247, 250)
BAR = (28, 28, 32)
CARD = (255, 255, 255)
ACCENT = (60, 120, 240)


def rect(img, x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            img.set(x, y, color)


def screen(button_y=250, accent=ACCENT, rows=3):
    img = png.Image.blank(W, H, BG)
    rect(img, 0, 0, W, 28, BAR)              # status bar
    rect(img, 12, 40, W - 12, 64, (220, 220, 228))   # title placeholder
    for i in range(rows):
        top = 76 + i * 46
        rect(img, 12, top, W - 12, top + 38, CARD)
        rect(img, 20, top + 10, 90, top + 18, (210, 210, 218))
        rect(img, 20, top + 24, 60, top + 30, (232, 232, 238))
    rect(img, 12, button_y, W - 12, button_y + 40, accent)  # call to action
    rect(img, 0, H - 44, W, H, (238, 238, 244))             # tab bar
    return img


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    baseline = os.path.join(root, ".shots", "baseline")
    current = os.path.join(root, ".shots", "current")
    os.makedirs(baseline, exist_ok=True)
    os.makedirs(current, exist_ok=True)

    # Baseline: what was approved.
    png.write(os.path.join(baseline, "01_launch.png"), screen())
    png.write(os.path.join(baseline, "02_cart_empty.png"), screen(rows=0))
    png.write(os.path.join(baseline, "03_cart_filled.png"), screen(rows=4))
    png.write(os.path.join(baseline, "04_catalog_dark.png"), screen(accent=(90, 90, 110)))

    # This run.
    png.write(os.path.join(current, "01_launch.png"), screen())                  # same
    png.write(os.path.join(current, "02_cart_empty.png"), screen(rows=0,
                                                                button_y=262))   # moved
    png.write(os.path.join(current, "03_cart_filled.png"), screen(rows=4,
                                                                 accent=(240, 70, 60)))
    png.write(os.path.join(current, "05_settings.png"), screen(rows=2))          # new

    print("drew 4 baseline and 4 current screenshots")
    return subprocess.call([
        sys.executable, "-m", "xcshot", "compare",
        "--baseline", baseline,
        "--current", current,
        "--diff", os.path.join(root, ".shots", "diff"),
        "--report", os.path.join(root, ".shots", "report.html"),
        "--tolerance", "8",
        "--threshold", "0.001",
        "--device", "demo, no simulator",
    ], cwd=root)


if __name__ == "__main__":
    sys.exit(main())
