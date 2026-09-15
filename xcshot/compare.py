"""Comparing a screenshot against its baseline.

A pixel counts as changed when any channel differs by more than `tolerance`.
That single knob absorbs the noise a simulator produces between runs (text
antialiasing, gradients) without hiding a real layout shift, because a real
shift moves whole blocks of pixels, not single channels by one or two steps.

A case fails when the share of changed pixels is above `threshold`.
"""

import os

from . import png

# Colours of the diff image.
DIFF_TINT = (255, 45, 85)
FADE = 0.18  # how much of the baseline stays visible under the tint


class Result:
    """Outcome for one screenshot: pass, fail, new or missing."""

    __slots__ = (
        "name",
        "status",
        "changed_pixels",
        "total_pixels",
        "ratio",
        "threshold",
        "baseline_path",
        "current_path",
        "diff_path",
        "message",
    )

    def __init__(self, name, status, message="", **kw):
        self.name = name
        self.status = status
        self.message = message
        self.changed_pixels = kw.get("changed_pixels", 0)
        self.total_pixels = kw.get("total_pixels", 0)
        self.ratio = kw.get("ratio", 0.0)
        self.threshold = kw.get("threshold", 0.0)
        self.baseline_path = kw.get("baseline_path")
        self.current_path = kw.get("current_path")
        self.diff_path = kw.get("diff_path")

    @property
    def ok(self):
        return self.status in ("pass", "new")

    @property
    def percent(self):
        return self.ratio * 100.0


def diff_images(baseline, current, tolerance=0):
    """Return (changed_pixel_count, diff image) for two images of equal size.

    The diff image is the baseline faded out, with every changed pixel painted
    in DIFF_TINT, so the change is readable in a thumbnail.
    """
    if baseline.size != current.size:
        raise ValueError(
            "size mismatch: baseline %dx%d, current %dx%d"
            % (baseline.width, baseline.height, current.width, current.height)
        )

    a, b = baseline.pixels, current.pixels
    out = bytearray(len(a))
    changed = 0
    for i in range(0, len(a), 3):
        dr = abs(a[i] - b[i])
        dg = abs(a[i + 1] - b[i + 1])
        db = abs(a[i + 2] - b[i + 2])
        if dr > tolerance or dg > tolerance or db > tolerance:
            changed += 1
            out[i : i + 3] = bytes(DIFF_TINT)
        else:
            out[i] = int(a[i] * FADE + 255 * (1 - FADE))
            out[i + 1] = int(a[i + 1] * FADE + 255 * (1 - FADE))
            out[i + 2] = int(a[i + 2] * FADE + 255 * (1 - FADE))

    return changed, png.Image(baseline.width, baseline.height, out)


def compare_case(name, baseline_path, current_path, diff_path, tolerance=0,
                 threshold=0.0):
    """Compare one screenshot and write its diff image when something moved."""
    if not os.path.exists(current_path):
        return Result(
            name,
            "missing",
            "no screenshot in this run, but a baseline exists",
            baseline_path=baseline_path,
        )
    if not os.path.exists(baseline_path):
        return Result(
            name,
            "new",
            "no baseline yet, accept this run to create one",
            current_path=current_path,
        )

    baseline = png.read(baseline_path)
    current = png.read(current_path)
    if baseline.size != current.size:
        return Result(
            name,
            "fail",
            "size changed: baseline %dx%d, current %dx%d"
            % (baseline.width, baseline.height, current.width, current.height),
            baseline_path=baseline_path,
            current_path=current_path,
            ratio=1.0,
            threshold=threshold,
        )

    changed, diff = diff_images(baseline, current, tolerance)
    total = baseline.width * baseline.height
    ratio = changed / total if total else 0.0

    written_diff = None
    if changed:
        os.makedirs(os.path.dirname(diff_path) or ".", exist_ok=True)
        png.write(diff_path, diff)
        written_diff = diff_path

    return Result(
        name,
        "fail" if ratio > threshold else "pass",
        "%d of %d pixels differ" % (changed, total),
        changed_pixels=changed,
        total_pixels=total,
        ratio=ratio,
        threshold=threshold,
        baseline_path=baseline_path,
        current_path=current_path,
        diff_path=written_diff,
    )


def compare_run(baseline_dir, current_dir, diff_dir, tolerance=0, threshold=0.0):
    """Compare every screenshot of a run, baseline and current side by side."""
    names = set()
    for directory in (baseline_dir, current_dir):
        if os.path.isdir(directory):
            names.update(
                f[:-4] for f in os.listdir(directory) if f.lower().endswith(".png")
            )

    return [
        compare_case(
            name,
            os.path.join(baseline_dir, name + ".png"),
            os.path.join(current_dir, name + ".png"),
            os.path.join(diff_dir, name + ".png"),
            tolerance=tolerance,
            threshold=threshold,
        )
        for name in sorted(names)
    ]
