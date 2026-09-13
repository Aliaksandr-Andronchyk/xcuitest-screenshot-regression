"""Suite configuration: which shots, how strict, what to ignore.

The config is JSON so that both the Swift side and the Python side can read it
without a dependency. A missing config is fine; defaults then apply to every
shot found on disk.

    {
      "channel_tolerance": 2,
      "max_diff_ratio": 0.001,
      "ignore": ["0,0,1170,140"],
      "shots": {
        "paywall": {"max_diff_ratio": 0.01, "ignore": ["0,1800,1170,120"]}
      }
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict

from .compare import Policy, Region


@dataclass
class SuiteConfig:
    default: Policy = field(default_factory=Policy)
    per_shot: Dict[str, Policy] = field(default_factory=dict)

    def policy_for(self, name: str) -> Policy:
        return self.per_shot.get(name, self.default)


def _regions(raw):
    return tuple(
        Region.parse(item) if isinstance(item, str) else Region(**item) for item in raw or ()
    )


def _policy(raw, base: Policy) -> Policy:
    return Policy(
        channel_tolerance=int(raw.get("channel_tolerance", base.channel_tolerance)),
        max_diff_ratio=float(raw.get("max_diff_ratio", base.max_diff_ratio)),
        ignore=_regions(raw["ignore"]) if "ignore" in raw else base.ignore,
    )


def load(path) -> SuiteConfig:
    """Read a suite config, returning defaults when the file is absent."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        return SuiteConfig()

    default = _policy(raw, Policy())
    per_shot = {name: _policy(body, default) for name, body in (raw.get("shots") or {}).items()}
    return SuiteConfig(default=default, per_shot=per_shot)
