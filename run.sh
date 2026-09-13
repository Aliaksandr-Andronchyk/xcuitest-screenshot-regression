#!/usr/bin/env bash
# Full pass: boot a simulator, run the UI tests, pull the shots out of the
# result bundle, compare them with the baselines, open the HTML report.
#
#   ./run.sh                                  # defaults below
#   ./run.sh --device "iPhone 16 Pro" --os 18.2
#   ./run.sh --accept                         # promote this run to baselines
#
# Needs macOS with Xcode. Everything after extraction is plain Python and runs
# anywhere, which is what CI on a Linux box can still verify.
set -euo pipefail

SCHEME="${SCHEME:-App}"
PROJECT="${PROJECT:-App.xcodeproj}"
DEVICE="iPhone 16"
OS_VERSION="latest"
ACCEPT=0
OUT=".shots"

while [ $# -gt 0 ]; do
  case "$1" in
    --device) DEVICE="$2"; shift 2 ;;
    --os) OS_VERSION="$2"; shift 2 ;;
    --scheme) SCHEME="$2"; shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --accept) ACCEPT=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "непонятный аргумент: $1" >&2; exit 2 ;;
  esac
done

if ! command -v xcodebuild >/dev/null 2>&1; then
  echo "xcodebuild не найден: прогон по симулятору бывает только на macOS с Xcode" >&2
  echo "сравнение и отчёт при этом работают: python3 -m shotdiff demo" >&2
  exit 3
fi

RESULT="$OUT/run.xcresult"
rm -rf "$RESULT" "$OUT/actual" "$OUT/diff"
mkdir -p "$OUT"

DESTINATION="platform=iOS Simulator,name=$DEVICE"
[ "$OS_VERSION" != "latest" ] && DESTINATION="$DESTINATION,OS=$OS_VERSION"

echo "== прогон: $SCHEME на $DEVICE ($OS_VERSION)"
# Fixed status bar: 9:41, full bars, full battery. Without this the clock alone
# fails every shot that is not inside an ignore region.
BOOTED_ID="$(xcrun simctl list devices booted -j | python3 -c 'import json,sys;d=json.load(sys.stdin)["devices"];print(next((x["udid"] for v in d.values() for x in v), ""))')"
if [ -n "$BOOTED_ID" ]; then
  xcrun simctl status_bar "$BOOTED_ID" override \
    --time "09:41" --batteryState charged --batteryLevel 100 \
    --cellularMode active --cellularBars 4 --wifiMode active --wifiBars 3 || true
fi

set +e
xcodebuild test \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -destination "$DESTINATION" \
  -resultBundlePath "$RESULT" \
  -only-testing:UITests \
  CODE_SIGNING_ALLOWED=NO | tail -40
TEST_STATUS=${PIPESTATUS[0]}
set -e
[ "$TEST_STATUS" -ne 0 ] && echo "== тесты вернули $TEST_STATUS, снимки всё равно разберём"

export PYTHONPATH="$(cd "$(dirname "$0")/tools" && pwd)"
python3 -m shotdiff extract --xcresult "$RESULT" --out "$OUT/actual"

if [ "$ACCEPT" -eq 1 ]; then
  python3 -m shotdiff accept --actual "$OUT/actual" --baseline Baselines
  exit 0
fi

set +e
python3 -m shotdiff compare \
  --baseline Baselines --actual "$OUT/actual" \
  --diff "$OUT/diff" --report "$OUT/report" --device "$DEVICE, iOS $OS_VERSION"
DIFF_STATUS=$?
set -e

[ -t 1 ] && [ -f "$OUT/report/report.html" ] && open "$OUT/report/report.html" || true
exit "$DIFF_STATUS"
