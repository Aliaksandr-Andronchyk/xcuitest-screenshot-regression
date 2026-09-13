"""Tie it together: pair baselines with actuals, compare, report, accept."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from . import report
from .compare import Result, compare_files, summarize
from .config import SuiteConfig


def _names(directory: Path):
    return {path.stem: path for path in sorted(Path(directory).glob("*.png"))}


def run(baseline_dir, actual_dir, diff_dir, config: SuiteConfig) -> List[Result]:
    """Compare every shot present in either directory."""
    baselines = _names(Path(baseline_dir))
    actuals = _names(Path(actual_dir))
    diff_dir = Path(diff_dir)
    diff_dir.mkdir(parents=True, exist_ok=True)

    results: List[Result] = []
    for name in sorted(set(baselines) | set(actuals)):
        if name not in baselines:
            results.append(
                Result(
                    name=name,
                    status="new",
                    message="эталона нет, примите снимок командой accept",
                    actual_path=str(actuals[name]),
                )
            )
        elif name not in actuals:
            results.append(
                Result(
                    name=name,
                    status="missing",
                    message="эталон есть, а в прогоне снимка нет: тест не дошёл до экрана",
                    baseline_path=str(baselines[name]),
                )
            )
        else:
            results.append(
                compare_files(
                    name,
                    baselines[name],
                    actuals[name],
                    diff_dir / ("%s.png" % name),
                    config.policy_for(name),
                )
            )
    return results


def accept(actual_dir, baseline_dir, only=None) -> List[str]:
    """Promote fresh shots to baselines. The only way baselines ever change."""
    baseline_dir = Path(baseline_dir)
    baseline_dir.mkdir(parents=True, exist_ok=True)
    accepted = []
    for name, path in _names(Path(actual_dir)).items():
        if only and name not in only:
            continue
        shutil.copyfile(path, baseline_dir / ("%s.png" % name))
        accepted.append(name)
    return accepted


def publish(results: List[Result], out_dir, context=None):
    """Write report.html and report.json next to each other."""
    out_dir = Path(out_dir)
    html_path = report.write(results, out_dir / "report.html", context=context)
    json_path = report.write_json(results, out_dir / "report.json")
    return html_path, json_path


def exit_code(results: List[Result]) -> int:
    counts = summarize(results)
    return 1 if counts.get("failed") or counts.get("missing") else 0
