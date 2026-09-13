"""Command line: extract, compare, accept, demo.

    python3 -m shotdiff compare --baseline Baselines --actual .shots/actual
    python3 -m shotdiff extract --xcresult build/Test.xcresult --out .shots/actual
    python3 -m shotdiff accept --actual .shots/actual --baseline Baselines
    python3 -m shotdiff demo --out .shots/demo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config as config_mod
from . import demo as demo_mod
from . import runner
from .compare import summarize


def _add_common(parser):
    parser.add_argument("--baseline", default="Baselines", type=Path, help="папка с эталонами")
    parser.add_argument("--actual", default=".shots/actual", type=Path, help="папка со свежими снимками")


def build_parser():
    parser = argparse.ArgumentParser(prog="shotdiff", description="регресс скриншотов XCUITest")
    subs = parser.add_subparsers(dest="command", required=True)

    compare = subs.add_parser("compare", help="сравнить прогон с эталонами и собрать отчёт")
    _add_common(compare)
    compare.add_argument("--diff", default=".shots/diff", type=Path)
    compare.add_argument("--report", default=".shots/report", type=Path, help="куда класть report.html")
    compare.add_argument("--config", default="shotdiff.json", type=Path)
    compare.add_argument("--device", default="", help="подпись устройства в шапке отчёта")

    extract = subs.add_parser("extract", help="достать снимки из .xcresult (нужен macOS)")
    extract.add_argument("--xcresult", type=Path)
    extract.add_argument("--from-dir", type=Path, help="взять готовые PNG из папки")
    extract.add_argument("--out", default=".shots/actual", type=Path)

    accept = subs.add_parser("accept", help="принять свежие снимки как эталон")
    _add_common(accept)
    accept.add_argument("names", nargs="*", help="имена снимков, по умолчанию все")

    demo = subs.add_parser("demo", help="сгенерировать пример: эталоны, прогон, отчёт")
    demo.add_argument("--out", default=".shots/demo", type=Path)

    return parser


def _compare(args) -> int:
    suite = config_mod.load(args.config)
    results = runner.run(args.baseline, args.actual, args.diff, suite)
    context = {"устройство": args.device} if args.device else None
    html_path, _ = runner.publish(results, args.report, context=context)

    counts = summarize(results)
    for result in results:
        if result.status != "passed":
            print("  %-9s %s%s" % (result.status, result.name, ": " + result.message if result.message else ""))
    print(
        "снимков %d: совпало %d, разошлось %d, новых %d, пропало %d"
        % (
            counts["total"],
            counts.get("passed", 0),
            counts.get("failed", 0),
            counts.get("new", 0),
            counts.get("missing", 0),
        )
    )
    print("отчёт: %s" % html_path)
    return runner.exit_code(results)


def _extract(args) -> int:
    from . import xcresult

    if args.from_dir:
        written = xcresult.extract_from_directory(args.from_dir, args.out)
    elif args.xcresult:
        try:
            written = xcresult.extract(args.xcresult, args.out)
        except xcresult.ExtractError as exc:
            print("не вышло достать снимки: %s" % exc, file=sys.stderr)
            return 2
    else:
        print("нужен --xcresult или --from-dir", file=sys.stderr)
        return 2
    print("снимков достали: %d -> %s" % (len(written), args.out))
    return 0


def _accept(args) -> int:
    accepted = runner.accept(args.actual, args.baseline, only=set(args.names) or None)
    print("принято эталонами: %d (%s)" % (len(accepted), ", ".join(accepted) or "ничего"))
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "compare":
        return _compare(args)
    if args.command == "extract":
        return _extract(args)
    if args.command == "accept":
        return _accept(args)
    if args.command == "demo":
        return demo_mod.main(args.out)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
