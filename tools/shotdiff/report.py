"""Self-contained HTML report.

Images are embedded as base64 data URIs so the report survives being emailed,
attached to a CI job or opened from a random folder. For a failed shot the
report shows baseline, actual and diff side by side, plus a slider that wipes
between baseline and actual, which is how people actually spot a two-point
font change.
"""

from __future__ import annotations

import base64
import datetime
import html
import json
from pathlib import Path
from typing import List

from .compare import Result, summarize

_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 32px; font: 15px/1.5 -apple-system, "SF Pro Text", Segoe UI, Roboto, sans-serif; background: #f6f6f8; color: #16161a; }
@media (prefers-color-scheme: dark) { body { background: #131316; color: #ececf1; } .shot, header { background: #1d1d21 !important; } }
header { background: #fff; border-radius: 14px; padding: 20px 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
h1 { margin: 0 0 6px; font-size: 22px; }
.meta { opacity: .65; font-size: 13px; }
.tally { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
.pill { padding: 5px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
.pill.passed { background: #d8f5dd; color: #11602a; }
.pill.failed { background: #ffdbe2; color: #8c0f2c; }
.pill.new { background: #dce9ff; color: #10346f; }
.pill.missing { background: #f0e2c8; color: #6b4a06; }
.shot { background: #fff; border-radius: 14px; padding: 18px 22px; margin-bottom: 18px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
.shot h2 { margin: 0; font-size: 17px; display: flex; align-items: center; gap: 12px; cursor: pointer; }
.shot h2 .why { font-weight: 400; font-size: 13px; opacity: .7; margin-left: auto; }
.body { display: none; margin-top: 16px; }
.shot.open .body, .shot.failed .body { display: block; }
.frames { display: flex; gap: 16px; flex-wrap: wrap; }
figure { margin: 0; }
figcaption { font-size: 12px; opacity: .65; margin-bottom: 6px; }
img { max-width: 320px; border-radius: 8px; border: 1px solid rgba(128,128,128,.35); display: block; background: #fff; }
.wipe { position: relative; max-width: 320px; }
.wipe .over { position: absolute; inset: 0; overflow: hidden; width: 50%; border-radius: 8px 0 0 8px; }
.wipe .over img { border-radius: 8px; max-width: none; }
.wipe input { width: 100%; margin-top: 8px; }
.empty { opacity: .6; font-style: italic; }
footer { opacity: .55; font-size: 12px; margin-top: 28px; }
"""

_JS = """
document.querySelectorAll('.shot h2').forEach(h => h.onclick = () => h.parentNode.classList.toggle('open'));
document.querySelectorAll('.wipe').forEach(w => {
  const input = w.querySelector('input'), over = w.querySelector('.over'), img = over.querySelector('img');
  const sync = () => { over.style.width = input.value + '%'; img.style.width = w.querySelector('.base').clientWidth + 'px'; };
  input.oninput = sync; window.addEventListener('load', sync); sync();
});
"""

_STATUS_WORD = {
    "passed": "совпало",
    "failed": "разошлось",
    "new": "новый снимок",
    "missing": "нет в прогоне",
}


def _data_uri(path) -> str:
    if not path:
        return ""
    try:
        blob = Path(path).read_bytes()
    except OSError:
        return ""
    return "data:image/png;base64," + base64.b64encode(blob).decode("ascii")


def _figure(caption: str, path, extra_class: str = "") -> str:
    uri = _data_uri(path)
    if not uri:
        return ""
    cls = (' class="%s"' % extra_class) if extra_class else ""
    return '<figure><figcaption>%s</figcaption><img%s src="%s" alt="%s"></figure>' % (
        html.escape(caption),
        cls,
        uri,
        html.escape(caption),
    )


def _wipe(result: Result) -> str:
    base, actual = _data_uri(result.baseline_path), _data_uri(result.actual_path)
    if not base or not actual:
        return ""
    return (
        '<figure><figcaption>эталон / прогон, ползунок</figcaption>'
        '<div class="wipe"><img class="base" src="%s" alt="прогон">'
        '<div class="over"><img src="%s" alt="эталон"></div>'
        '<input type="range" min="0" max="100" value="50"></div></figure>'
    ) % (actual, base)


def _shot_block(result: Result) -> str:
    why = html.escape(result.message) if result.message else ""
    if result.status == "passed" and result.total_pixels:
        why = "%d пикселей, расхождений нет" % result.total_pixels
    frames = [
        _figure("эталон", result.baseline_path),
        _figure("прогон", result.actual_path),
        _figure("разница", result.diff_path),
    ]
    if result.status == "failed":
        frames.append(_wipe(result))
    inner = "".join(f for f in frames if f)
    if not inner:
        inner = '<p class="empty">нечего показать: файлов нет</p>'
    return (
        '<section class="shot %s"><h2><span class="pill %s">%s</span>%s'
        '<span class="why">%s</span></h2><div class="body"><div class="frames">%s</div></div></section>'
    ) % (
        result.status,
        result.status,
        _STATUS_WORD.get(result.status, result.status),
        html.escape(result.name),
        why,
        inner,
    )


def render(results: List[Result], title: str = "XCUITest: регресс по скриншотам", context=None) -> str:
    """Build the full HTML document."""
    counts = summarize(results)
    order = {"failed": 0, "missing": 1, "new": 2, "passed": 3}
    ordered = sorted(results, key=lambda r: (order.get(r.status, 9), r.name))

    pills = "".join(
        '<span class="pill %s">%s: %d</span>' % (key, _STATUS_WORD[key], counts.get(key, 0))
        for key in ("failed", "missing", "new", "passed")
        if counts.get(key, 0)
    ) or '<span class="pill new">снимков нет</span>'

    meta_bits = ["снимков: %d" % counts["total"]]
    for key, value in (context or {}).items():
        meta_bits.append("%s: %s" % (key, value))
    meta_bits.append(datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))

    return (
        "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>%s</title><style>%s</style></head><body>"
        '<header><h1>%s</h1><div class="meta">%s</div><div class="tally">%s</div></header>'
        "%s<footer>shotdiff, отчёт самодостаточный: картинки вшиты в файл</footer>"
        "<script>%s</script></body></html>\n"
    ) % (
        html.escape(title),
        _CSS,
        html.escape(title),
        html.escape(" · ".join(meta_bits)),
        pills,
        "".join(_shot_block(r) for r in ordered),
        _JS,
    )


def write(results: List[Result], path, title=None, context=None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"context": context}
    if title:
        kwargs["title"] = title
    path.write_text(render(results, **kwargs), encoding="utf-8")
    return path


def write_json(results: List[Result], path) -> Path:
    """Machine-readable twin of the report, for CI annotations."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summarize(results), "shots": [r.as_dict() for r in results]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
