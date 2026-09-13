"""Screenshot comparison: baseline against a fresh run.

The rules are deliberately boring, because a flaky differ is worse than none:

* a pixel differs when any RGBA channel is off by more than ``channel_tolerance``;
* a shot fails when the share of differing pixels exceeds ``max_diff_ratio``;
* differing sizes fail immediately, there is no scaling;
* ignore regions (blinking clock, battery, carrier) are excluded from counting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from . import png

DIFF_COLOR = (255, 0, 128, 255)
IGNORED_COLOR = (255, 214, 0, 255)


@dataclass(frozen=True)
class Region:
    """A rectangle excluded from comparison, in pixels."""

    x: int
    y: int
    width: int
    height: int

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    @classmethod
    def parse(cls, text: str) -> "Region":
        parts = text.replace(",", " ").split()
        if len(parts) != 4:
            raise ValueError("region must be 'x,y,width,height', got %r" % text)
        return cls(*(int(p) for p in parts))

    def as_dict(self):
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class Policy:
    """How strict the comparison is."""

    channel_tolerance: int = 0
    max_diff_ratio: float = 0.0
    ignore: Sequence[Region] = field(default_factory=tuple)


@dataclass
class Result:
    """Outcome for one screenshot."""

    name: str
    status: str  # passed | failed | new | missing
    diff_pixels: int = 0
    total_pixels: int = 0
    diff_ratio: float = 0.0
    message: str = ""
    baseline_path: Optional[str] = None
    actual_path: Optional[str] = None
    diff_path: Optional[str] = None
    bounds: Optional[Tuple[int, int, int, int]] = None

    @property
    def ok(self) -> bool:
        return self.status == "passed"

    def as_dict(self):
        data = {
            "name": self.name,
            "status": self.status,
            "diff_pixels": self.diff_pixels,
            "total_pixels": self.total_pixels,
            "diff_ratio": round(self.diff_ratio, 6),
            "message": self.message,
            "baseline": self.baseline_path,
            "actual": self.actual_path,
            "diff": self.diff_path,
        }
        if self.bounds:
            x0, y0, x1, y1 = self.bounds
            data["bounds"] = {"x": x0, "y": y0, "width": x1 - x0 + 1, "height": y1 - y0 + 1}
        return data


def compare_images(baseline: png.Image, actual: png.Image, policy: Policy):
    """Return ``(result_fields, diff_image)`` for two images of equal size.

    The diff image is the actual shot dimmed, with differing pixels painted
    magenta and ignored regions painted amber, so a human can see at a glance
    both what moved and what we chose not to look at.
    """
    if baseline.size != actual.size:
        raise ValueError(
            "size changed: baseline %dx%d, actual %dx%d"
            % (baseline.width, baseline.height, actual.width, actual.height)
        )

    width, height = baseline.width, baseline.height
    diff = png.Image.blank(width, height)
    base_px, act_px, diff_px = baseline.pixels, actual.pixels, diff.pixels

    ignored = bytearray(width * height)
    for region in policy.ignore:
        for y in range(max(0, region.y), min(height, region.y + region.height)):
            row = y * width
            for x in range(max(0, region.x), min(width, region.x + region.width)):
                ignored[row + x] = 1

    tolerance = policy.channel_tolerance
    changed = 0
    counted = 0
    min_x, min_y, max_x, max_y = width, height, -1, -1

    for i in range(width * height):
        o = i * 4
        if ignored[i]:
            diff_px[o : o + 4] = bytes(IGNORED_COLOR)
            continue
        counted += 1
        differs = False
        for c in range(4):
            if abs(base_px[o + c] - act_px[o + c]) > tolerance:
                differs = True
                break
        if differs:
            changed += 1
            diff_px[o : o + 4] = bytes(DIFF_COLOR)
            x, y = i % width, i // width
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
        else:
            # dim the unchanged background so the magenta stands out
            diff_px[o] = act_px[o] // 3 + 170
            diff_px[o + 1] = act_px[o + 1] // 3 + 170
            diff_px[o + 2] = act_px[o + 2] // 3 + 170
            diff_px[o + 3] = 255

    ratio = changed / counted if counted else 0.0
    bounds = (min_x, min_y, max_x, max_y) if max_x >= 0 else None
    return (changed, counted, ratio, bounds), diff


def compare_files(name: str, baseline_path, actual_path, diff_path, policy: Policy) -> Result:
    """Compare two PNG files on disk and write the diff image when they differ."""
    try:
        baseline = png.load(baseline_path)
        actual = png.load(actual_path)
    except (OSError, png.PngError) as exc:
        return Result(name=name, status="failed", message=str(exc))

    try:
        (changed, counted, ratio, bounds), diff = compare_images(baseline, actual, policy)
    except ValueError as exc:
        return Result(
            name=name,
            status="failed",
            message=str(exc),
            baseline_path=str(baseline_path),
            actual_path=str(actual_path),
        )

    passed = ratio <= policy.max_diff_ratio
    result = Result(
        name=name,
        status="passed" if passed else "failed",
        diff_pixels=changed,
        total_pixels=counted,
        diff_ratio=ratio,
        baseline_path=str(baseline_path),
        actual_path=str(actual_path),
        bounds=bounds,
    )
    if not passed:
        png.save(diff, diff_path)
        result.diff_path = str(diff_path)
        result.message = "разошлось %d пикселей из %d (%.3f%%), бюджет %.3f%%" % (
            changed,
            counted,
            ratio * 100,
            policy.max_diff_ratio * 100,
        )
    return result


def summarize(results: List[Result]):
    counts = {"passed": 0, "failed": 0, "new": 0, "missing": 0}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    counts["total"] = len(results)
    return counts
