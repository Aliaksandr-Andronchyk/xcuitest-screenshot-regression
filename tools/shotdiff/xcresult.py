"""Pull screenshot attachments out of an .xcresult bundle.

Runs ``xcrun xcresulttool`` and therefore only works on a Mac with Xcode. The
rest of shotdiff works on any machine with Python, which is why extraction
lives alone in this module.

XCUITest attaches our shots with ``XCTAttachment`` named ``shot:<name>``; we
export exactly those and drop everything else (automatic screenshots, logs).
"""

from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
from pathlib import Path

ATTACHMENT_PREFIX = "shot:"


class ExtractError(RuntimeError):
    pass


def _xcresulttool(args, binary=False):
    command = ["xcrun", "xcresulttool"] + args
    try:
        done = subprocess.run(command, capture_output=True, check=True)
    except FileNotFoundError as exc:
        raise ExtractError("xcrun is not available, extraction needs macOS with Xcode") from exc
    except subprocess.CalledProcessError as exc:
        raise ExtractError(
            "%s failed: %s" % (" ".join(command), exc.stderr.decode("utf-8", "replace").strip())
        ) from exc
    return done.stdout if binary else json.loads(done.stdout)


def _walk(node, found):
    """Collect ``(name, payload_id)`` pairs from the result graph."""
    if isinstance(node, dict):
        if node.get("_type", {}).get("_name") == "ActionTestAttachment":
            name = node.get("name", {}).get("_value", "")
            payload = node.get("payloadRef", {}).get("id", {}).get("_value")
            if name.startswith(ATTACHMENT_PREFIX) and payload:
                found.append((name[len(ATTACHMENT_PREFIX) :], payload))
        for value in node.values():
            _walk(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk(value, found)
    return found


def _attachments_via_graph(bundle: Path):
    root = _xcresulttool(["get", "--legacy", "--format", "json", "--path", str(bundle)])
    found = []
    _walk(root, found)
    queue = [
        ref["id"]["_value"]
        for ref in _collect_refs(root)
        if isinstance(ref, dict) and "id" in ref
    ]
    seen = set()
    while queue:
        ref_id = queue.pop()
        if ref_id in seen:
            continue
        seen.add(ref_id)
        try:
            node = _xcresulttool(
                ["get", "--legacy", "--format", "json", "--path", str(bundle), "--id", ref_id]
            )
        except ExtractError:
            continue
        _walk(node, found)
        queue.extend(
            ref["id"]["_value"] for ref in _collect_refs(node) if isinstance(ref, dict) and "id" in ref
        )
    # de-duplicate, keeping the last shot with a given name
    return dict(found)


def _collect_refs(node, out=None):
    out = [] if out is None else out
    if isinstance(node, dict):
        if node.get("_type", {}).get("_name") == "Reference":
            out.append(node)
        for value in node.values():
            _collect_refs(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_refs(value, out)
    return out


def extract(bundle, destination) -> dict:
    """Export ``shot:*`` attachments from ``bundle`` into ``destination``.

    Returns a mapping of shot name to written path.
    """
    bundle = Path(bundle)
    destination = Path(destination)
    if not bundle.exists():
        raise ExtractError("no such result bundle: %s" % bundle)
    destination.mkdir(parents=True, exist_ok=True)

    written = {}
    for name, payload_id in _attachments_via_graph(bundle).items():
        data = _xcresulttool(
            ["export", "--legacy", "--type", "file", "--path", str(bundle), "--id", payload_id],
            binary=True,
        )
        path = destination / ("%s.png" % name)
        path.write_bytes(data)
        written[name] = path
    return written


def extract_from_directory(source, destination) -> dict:
    """Copy already-exported PNGs, for simulators driven outside xcodebuild.

    Useful when shots are produced by ``simctl io ... screenshot`` or lifted
    from the app container: the rest of the pipeline does not care who took
    the picture.
    """
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    written = {}
    for path in sorted(source.glob("*.png")):
        target = destination / path.name
        if path.resolve() != target.resolve():
            shutil.copyfile(path, target)
        written[path.stem] = target
    return written


def simulator_metadata(bundle) -> dict:
    """Best-effort device and OS of the run, for the report header."""
    info = Path(bundle) / "Info.plist"
    try:
        with open(info, "rb") as fh:
            return plistlib.load(fh)
    except (OSError, plistlib.InvalidFileException):
        return {}
