"""Shared config loading and model resolution for the TierwiseAgents scripts.

Standard library only.
"""

import json
import sys
from pathlib import Path

TIER_DEFAULTS = {"top": "opus", "mid": "sonnet", "small": "haiku"}
ROLE_TIER = {
    "architect": "top",
    "builder": "mid",
    "tester": "mid",
    "reviewer": "mid",
    "debugger": "mid",
    "scout": "small",
    "runner": "small",
}
ALIASES = {"fable", "opus", "sonnet", "haiku"}
SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_NAME = "tierwise.json"


def agent_name(role):
    return f"tw-{role}"


def load_config(start=None):
    """Return (config dict, path) from the project file, else the user file."""
    for base in (Path(start) if start else Path.cwd(), Path.home()):
        path = base / ".claude" / CONFIG_NAME
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                sys.exit(f"error: {path} is not valid JSON: {e}")
            if not isinstance(data, dict):
                sys.exit(f"error: {path} must hold a JSON object")
            return data, path
    return {}, None


def _classify(value, where):
    if isinstance(value, dict):
        command = value.get("command")
        if not isinstance(command, str) or not command.strip():
            sys.exit(f"error: {where} needs a non-empty \"command\" string")
        return {"kind": "command", "value": command}
    if isinstance(value, str) and value.strip():
        value = value.strip()
        return {"kind": "alias" if value in ALIASES else "model", "value": value}
    sys.exit(f"error: {where} must be a model name or {{\"command\": ...}}")


def resolve(config):
    """Return {role: {"tier", "kind", "value"}} for every role.

    Order: roles.<role>, then tiers.<tier>, then the default (fable for the
    top tier when allowFable is set). Fable is never used without allowFable.
    """
    allow_fable = bool(config.get("allowFable"))
    tiers = config.get("tiers") or {}
    roles = config.get("roles") or {}
    for key in roles:
        if key not in ROLE_TIER:
            sys.exit(f"error: unknown role {key!r}; roles are {', '.join(ROLE_TIER)}")
    for key in tiers:
        if key not in TIER_DEFAULTS:
            sys.exit(f"error: unknown tier {key!r}; tiers are top, mid, small")

    out = {}
    for role, tier in ROLE_TIER.items():
        default = "fable" if (tier == "top" and allow_fable) else TIER_DEFAULTS[tier]
        if role in roles:
            entry = _classify(roles[role], f"roles.{role}")
        elif tier in tiers:
            entry = _classify(tiers[tier], f"tiers.{tier}")
        else:
            entry = {"kind": "alias", "value": default}
        if entry["value"] == "fable" and entry["kind"] == "alias" and not allow_fable:
            entry = {"kind": "alias", "value": TIER_DEFAULTS[tier]}
        out[role] = {"tier": tier, **entry}
    return out
