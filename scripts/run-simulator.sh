#!/usr/bin/env bash
#
# One run: boot a simulator, run the UI tests, extract the screenshots,
# compare them against the baseline, write the HTML report.
#
# Needs macOS with Xcode. Everything after the extract step is plain Python
# and can be run on any machine against the PNGs this script produced.
#
#   ./scripts/run-simulator.sh
#   DEVICE="iPhone 15 Pro" OS="17.5" ./scripts/run-simulator.sh
#   SCHEME=MyApp PROJECT=MyApp.xcodeproj ./scripts/run-simulator.sh

set -euo pipefail

DEVICE="${DEVICE:-iPhone 15}"
OS="${OS:-latest}"
SCHEME="${SCHEME:-App}"
PROJECT="${PROJECT:-}"
WORKSPACE="${WORKSPACE:-}"
TEST_PLAN="${TEST_PLAN:-}"
OUT="${OUT:-build}"
SHOTS="${SHOTS:-shots}"
TOLERANCE="${TOLERANCE:-8}"
THRESHOLD="${THRESHOLD:-0.001}"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if ! command -v xcodebuild >/dev/null 2>&1; then
  echo "xcodebuild not found: this script needs macOS with Xcode." >&2
  echo "The comparison alone runs anywhere: python3 -m xcshot compare --help" >&2
  exit 2
fi

result="$OUT/Result.xcresult"
rm -rf "$result" "$SHOTS/current" "$SHOTS/diff"
mkdir -p "$OUT"

target=()
if [ -n "$WORKSPACE" ]; then
  target=(-workspace "$WORKSPACE")
elif [ -n "$PROJECT" ]; then
  target=(-project "$PROJECT")
fi

plan=()
if [ -n "$TEST_PLAN" ]; then
  plan=(-testPlan "$TEST_PLAN")
fi

echo "==> simulator: $DEVICE ($OS), scheme: $SCHEME"

# A named simulator that is already booted is reused; xcodebuild boots it
# otherwise. -resultBundlePath is what makes the screenshots reachable later.
set +e
xcodebuild test \
  "${target[@]}" \
  -scheme "$SCHEME" \
  "${plan[@]}" \
  -destination "platform=iOS Simulator,name=$DEVICE,OS=$OS" \
  -resultBundlePath "$result" \
  -only-testing:UITests \
  ONLY_ACTIVE_ARCH=YES \
  CODE_SIGNING_ALLOWED=NO
test_status=$?
set -e

# A failing test still leaves its screenshots in the bundle, and those
# screenshots are usually the reason it failed, so keep going and report.
if [ "$test_status" -ne 0 ]; then
  echo "==> xcodebuild test exited with $test_status, comparing anyway"
fi

echo "==> extracting screenshots"
python3 -m xcshot extract "$result" --out "$SHOTS/current"

echo "==> comparing against the baseline"
set +e
XCSHOT_DEVICE="$DEVICE ($OS)" python3 -m xcshot compare \
  --baseline "$SHOTS/baseline" \
  --current "$SHOTS/current" \
  --diff "$SHOTS/diff" \
  --report "$SHOTS/report.html" \
  --tolerance "$TOLERANCE" \
  --threshold "$THRESHOLD"
compare_status=$?
set -e

echo "==> report: $SHOTS/report.html"
if [ "$test_status" -ne 0 ]; then
  exit "$test_status"
fi
exit "$compare_status"
