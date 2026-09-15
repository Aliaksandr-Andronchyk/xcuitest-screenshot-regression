"""Pulling screenshots out of an .xcresult bundle.

XCUITest does not write PNG files anywhere useful: it stores them as
attachments inside the result bundle. `xcrun xcresulttool` is the only
supported way to read that bundle, so this module shells out to it.

Runs on macOS with Xcode installed. Everything else in xcshot is plain Python
and works anywhere, which is what makes the comparison testable off a Mac.
"""

import json
import os
import re
import subprocess

SUFFIX = re.compile(r"_\d+_[0-9A-F-]{36}\.png$", re.IGNORECASE)


class ExtractError(Exception):
    pass


def _xcresulttool(*args):
    cmd = ["xcrun", "xcresulttool"] + list(args)
    try:
        done = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError:
        raise ExtractError("xcrun not found: this step needs macOS with Xcode")
    if done.returncode != 0:
        raise ExtractError(
            "%s failed: %s" % (" ".join(cmd), done.stderr.decode("utf-8", "replace").strip())
        )
    return done.stdout


def _get(node, key):
    """Read one field out of xcresulttool's verbose typed JSON."""
    value = node.get(key)
    if value is None:
        return None
    if isinstance(value, dict) and "_value" in value:
        return value["_value"]
    if isinstance(value, dict) and "_values" in value:
        return value["_values"]
    return value


def _walk(node, bundle, out):
    """Collect (filename, payload id) for every PNG attachment in the tree."""
    for attachment in _get(node, "attachments") or []:
        name = _get(attachment, "filename") or _get(attachment, "name") or ""
        payload = attachment.get("payloadRef") or {}
        payload_id = _get(payload, "id")
        if name.lower().endswith(".png") and payload_id:
            out.append((name, payload_id))

    for key in ("subtests", "activitySummaries", "subactivities"):
        for child in _get(node, key) or []:
            _walk(child, bundle, out)


def clean_name(filename):
    """`Cart_empty_1_A1B2...-UUID.png` -> `Cart_empty`.

    XCUITest appends an index and a UUID to every attachment name. The test
    code chose the name on purpose, so the suffix is noise.
    """
    return SUFFIX.sub("", filename) or os.path.splitext(filename)[0]


def extract(bundle, dest):
    """Write every screenshot attachment of `bundle` into `dest` as <name>.png.

    Returns the list of names written.
    """
    if not os.path.exists(bundle):
        raise ExtractError("no result bundle at %s" % bundle)
    os.makedirs(dest, exist_ok=True)

    root = json.loads(_xcresulttool("get", "--path", bundle, "--format", "json"))
    found = []
    for action in _get(root, "actions") or []:
        result = action.get("actionResult") or {}
        tests_id = _get(result.get("testsRef") or {}, "id")
        if not tests_id:
            continue
        tests = json.loads(
            _xcresulttool("get", "--path", bundle, "--id", tests_id, "--format", "json")
        )
        for summary in _get(tests, "summaries") or []:
            for testable in _get(summary, "testableSummaries") or []:
                for test in _get(testable, "tests") or []:
                    _walk(test, bundle, found)

    written = []
    for filename, payload_id in found:
        name = clean_name(filename)
        target = os.path.join(dest, name + ".png")
        _xcresulttool("export", "--path", bundle, "--id", payload_id,
                      "--type", "file", "--output-path", target)
        written.append(name)
    return written
