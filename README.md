# xcuitest-screenshot-regression

Screenshot regression around an XCUITest run: drive the app on a simulator,
take named screenshots, compare them against approved baselines pixel by pixel,
and write one HTML report a human can judge in five seconds.

A UI test that only asserts "the button exists" passes while the button sits
half off screen. This catches that, and it shows the baseline, the fresh shot
and the difference painted in magenta, side by side.

## What is inside

| Path | What it is |
|---|---|
| `run.sh` | The whole pass: `xcodebuild test` on a simulator, extract, compare, report |
| `UITests/ScreenshotRegression.swift` | Test-side helper: deterministic launch, wait until the UI is still, attach the shot |
| `UITests/AppScreenshotTests.swift` | Example suite: feed, detail, paywall, settings, dark mode |
| `tools/shotdiff/xcresult.py` | Screenshots out of an `.xcresult` bundle via `xcresulttool` (macOS only) |
| `tools/shotdiff/png.py` | 8-bit PNG read and write, standard library only |
| `tools/shotdiff/compare.py` | Baseline against actual: tolerance, budget, ignore regions, diff image |
| `tools/shotdiff/report.py` | `report.html` with the images embedded, plus `report.json` for CI |
| `tools/shotdiff/demo.py` | The whole comparison end to end without a Mac |
| `shotdiff.json` | Budgets and ignore regions, per suite and per shot |
| `tests/test_shotdiff.py` | Tests for everything that does not need a Mac |

Only the extract step needs macOS with Xcode. The rest is plain Python with no
dependencies, so the comparison runs and is tested on any machine, including a
Linux CI box working on PNGs a Mac produced.

## Run it

On a Mac, against your app:

```sh
SCHEME=MyApp PROJECT=MyApp.xcodeproj ./run.sh --device "iPhone 16 Pro" --os 18.2
./run.sh --accept            # promote this run to the baselines
```

Anywhere, to see the tool work on synthetic screens:

```sh
PYTHONPATH=tools python3 -m shotdiff demo --out .shots/demo
open .shots/demo/report/report.html      # xdg-open on Linux
```

Tests:

```sh
python3 -m unittest discover -s tests -v
```

## The loop

1. Run. The first run has no baselines: every shot comes out as `new`.
2. Open `report.html` and look at what the run produced.
3. Accept what is correct: `python3 -m shotdiff accept --actual .shots/actual
   --baseline Baselines`, or name single shots to accept only those.
4. Commit `Baselines/`. They are source, same as the tests.
5. From then on `failed` means pixels moved that nobody approved, and `run.sh`
   exits non-zero, so CI stops.

`missing` also fails the run: a shot the baseline knows about but the run never
took usually means the test did not reach that screen.

## The knobs, in `shotdiff.json`

```json
{
  "channel_tolerance": 2,
  "max_diff_ratio": 0.0005,
  "ignore": ["0,0,1179,140"],
  "shots": { "paywall": { "max_diff_ratio": 0.004 } }
}
```

- `channel_tolerance` (0-255): per channel difference that still counts as
  equal. Absorbs simulator antialiasing noise.
- `max_diff_ratio`: share of pixels that may differ before the shot fails.
  `0.0005` is one pixel in two thousand.
- `ignore`: rectangles in screenshot pixels, `x,y,width,height`, excluded from
  counting and painted amber in the diff, so it is visible what was not looked
  at. The status bar is the usual one.

Start strict, loosen one knob at a time, and only after looking at why a run is
noisy: every step up hides real changes too.

## Keeping runs repeatable

- `run.sh` pins the simulator status bar to 9:41, full bars, full battery.
- The app has to honour `-UITest`: seeded data, no onboarding, no animations,
  frozen clock. That contract is the difference between a suite and a lottery.
- Shots are taken after the UI stops moving, never after a `sleep`.
- One device and one OS version per baseline folder. A baseline taken on an
  iPhone 16 does not describe an iPhone SE.
- Shot names are stable strings: the name becomes the file name.

## Licence

MIT.
