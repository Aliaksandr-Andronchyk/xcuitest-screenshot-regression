"""xcshot command line: extract, compare, report, accept.

    python3 -m xcshot extract build/Result.xcresult --out shots/current
    python3 -m xcshot compare --baseline shots/baseline --current shots/current
    python3 -m xcshot accept --baseline shots/baseline --current shots/current

`compare` exits 1 when anything failed, so CI stops on a visual regression.
"""

import argparse
import os
import shutil
import sys

from . import compare as compare_mod
from . import report as report_mod

DEFAULT_BASELINE = "shots/baseline"
DEFAULT_CURRENT = "shots/current"
DEFAULT_DIFF = "shots/diff"
DEFAULT_REPORT = "shots/report.html"

STATUS_MARK = {"pass": "ok  ", "fail": "FAIL", "new": "new ", "missing": "MISS"}


def _dirs(parser):
    parser.add_argument("--baseline", default=DEFAULT_BASELINE,
                        help="folder with approved screenshots")
    parser.add_argument("--current", default=DEFAULT_CURRENT,
                        help="folder with screenshots of this run")


def cmd_extract(args):
    from . import attachments

    names = attachments.extract(args.bundle, args.out)
    for name in names:
        print("%s.png" % name)
    print("%d screenshot(s) into %s" % (len(names), args.out))
    return 0


def cmd_compare(args):
    results = compare_mod.compare_run(
        args.baseline, args.current, args.diff,
        tolerance=args.tolerance, threshold=args.threshold,
    )
    if not results:
        print("no screenshots found in %s or %s" % (args.baseline, args.current))
        return 1

    for r in results:
        line = "%s %-40s %s" % (STATUS_MARK.get(r.status, r.status), r.name, r.message)
        print(line.rstrip())

    report_mod.write(args.report, results, device=args.device)
    print("report: %s" % args.report)

    failed = [r for r in results if not r.ok]
    print("%d of %d cases failed" % (len(failed), len(results)))
    return 1 if failed else 0


def cmd_accept(args):
    os.makedirs(args.baseline, exist_ok=True)
    moved = 0
    for filename in sorted(os.listdir(args.current)):
        if not filename.lower().endswith(".png"):
            continue
        if args.only and os.path.splitext(filename)[0] not in args.only:
            continue
        shutil.copyfile(
            os.path.join(args.current, filename),
            os.path.join(args.baseline, filename),
        )
        print("accepted %s" % filename)
        moved += 1
    print("%d screenshot(s) are the baseline now" % moved)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="xcshot", description="Screenshot regression for XCUITest runs"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="pull screenshots out of an .xcresult")
    extract.add_argument("bundle", help="path to the .xcresult bundle")
    extract.add_argument("--out", default=DEFAULT_CURRENT, help="where to put the PNGs")
    extract.set_defaults(func=cmd_extract)

    compare = sub.add_parser("compare", help="compare a run against the baseline")
    _dirs(compare)
    compare.add_argument("--diff", default=DEFAULT_DIFF, help="where to put diff images")
    compare.add_argument("--report", default=DEFAULT_REPORT, help="HTML report path")
    compare.add_argument("--tolerance", type=int, default=0,
                         help="per channel difference that still counts as equal (0-255)")
    compare.add_argument("--threshold", type=float, default=0.0,
                         help="share of changed pixels a case may have, 0.001 is 0.1%%")
    compare.add_argument("--device", default=os.environ.get("XCSHOT_DEVICE", ""),
                         help="simulator name, shown in the report")
    compare.set_defaults(func=cmd_compare)

    accept = sub.add_parser("accept", help="make the current run the new baseline")
    _dirs(accept)
    accept.add_argument("--only", nargs="*", default=None,
                        help="accept only these case names")
    accept.set_defaults(func=cmd_accept)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
