#!/usr/bin/env python3
"""Configure the model orchestrator.

Writes model-orchestrator.json and generates the mo-* agents with the chosen
models pinned in their frontmatter. Standard library only.

    python3 setup.py
    python3 setup.py --allow-fable
    python3 setup.py --mid claude-sonnet-5-5 --role reviewer=opus
    python3 setup.py --small-cmd 'opencode run -m <provider/model> {prompt}'
    python3 setup.py --gate lint='npm run lint' --gate test='npm test'
"""

import argparse
import json
import re
import shlex
import sys
from pathlib import Path

from mo_config import (ALIASES, CONFIG_NAME, ROLE_TIER, SKILL_DIR, TIER_DEFAULTS,
                       agent_name, load_config, resolve)

MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\[\]@-]*$")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scope", choices=["project", "user"], default="project",
                   help="write to ./.claude (project) or ~/.claude (user)")
    p.add_argument("--top", help="model for the top tier (default: opus, or fable with --allow-fable)")
    p.add_argument("--mid", help="model for the mid tier (default: sonnet)")
    p.add_argument("--small", help="model for the small tier (default: haiku)")
    for tier in TIER_DEFAULTS:
        p.add_argument(f"--{tier}-cmd", metavar="COMMAND",
                       help=f"run the {tier} tier on an external CLI, e.g. a non-Claude coding agent")
    p.add_argument("--role", action="append", default=[], metavar="ROLE=MODEL",
                   help="override one role, e.g. reviewer=opus (repeatable)")
    p.add_argument("--gate", action="append", default=[], metavar="NAME=COMMAND",
                   help="a quality gate that must pass before a push, in order (repeatable)")
    p.add_argument("--allow-fable", action="store_true",
                   help="allow Fable; the top tier uses it unless --top is given")
    p.add_argument("--dry-run", action="store_true", help="print the result, write nothing")
    return p.parse_args()


def check_model(value, flag):
    if not MODEL_ID.match(value):
        sys.exit(f"error: {flag} {value!r} is not a valid model name")
    return value


def pin_model(text, model):
    """Replace the model line inside the frontmatter of an agent file."""
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("agent template has no frontmatter")
    front, n = re.subn(r"(?m)^model:.*$", f"model: {model}", parts[1], count=1)
    if n == 0:
        front = front.rstrip("\n") + f"\nmodel: {model}\n"
    return "---" + front + "---" + parts[2]


def main():
    args = parse_args()
    base = (Path.home() if args.scope == "user" else Path.cwd()) / ".claude"
    config_path = base / CONFIG_NAME

    # Start from the existing file in this scope so repeated runs add to it.
    config = {}
    if config_path.is_file():
        config, _ = load_config(base.parent)
    tiers = dict(config.get("tiers") or {})
    roles = dict(config.get("roles") or {})
    gates = list(config.get("gates") or [])
    allow_fable = bool(config.get("allowFable")) or args.allow_fable

    for tier in TIER_DEFAULTS:
        model, command = getattr(args, tier), getattr(args, f"{tier}_cmd")
        if model and command:
            sys.exit(f"error: give --{tier} or --{tier}-cmd, not both")
        if model:
            tiers[tier] = check_model(model.strip(), f"--{tier}")
        if command:
            try:
                if not shlex.split(command):
                    raise ValueError("empty command")
            except ValueError as e:
                sys.exit(f"error: --{tier}-cmd: {e}")
            tiers[tier] = {"command": command}

    for item in args.role:
        role, sep, model = item.partition("=")
        if not sep or role not in ROLE_TIER:
            sys.exit(f"error: --role expects ROLE=MODEL with a role from: {', '.join(ROLE_TIER)}")
        roles[role] = check_model(model.strip(), f"--role {role}=")

    if args.gate:
        gates = []
        for item in args.gate:
            name, sep, command = item.partition("=")
            if not sep or not name.strip() or not command.strip():
                sys.exit("error: --gate expects NAME=COMMAND")
            gates.append({"name": name.strip(), "command": command.strip()})

    chosen = [v for v in list(tiers.values()) + list(roles.values()) if isinstance(v, str)]
    if "fable" in chosen and not allow_fable:
        sys.exit("error: fable is selected; pass --allow-fable to confirm")

    config = {"allowFable": allow_fable}
    if tiers:
        config["tiers"] = tiers
    if roles:
        config["roles"] = roles
    if gates:
        config["gates"] = gates
    resolved = resolve(config)

    outputs = {config_path: json.dumps(config, indent=2) + "\n"}
    for role, entry in resolved.items():
        shown = f"command: {entry['value']}" if entry["kind"] == "command" else entry["value"]
        print(f"{entry['tier']:<5} {agent_name(role):<13} -> {shown}")
        if entry["kind"] == "command":
            continue  # external command: no Claude agent to generate
        template = SKILL_DIR / "agents" / f"{agent_name(role)}.md"
        if not template.is_file():
            sys.exit(f"error: missing agent template {template}")
        outputs[base / "agents" / f"{agent_name(role)}.md"] = pin_model(
            template.read_text(encoding="utf-8"), entry["value"])
    for gate in gates:
        print(f"gate  {gate['name']:<13} -> {gate['command']}")

    for path, content in outputs.items():
        if args.dry_run:
            print(f"would write {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path}")
    if not args.dry_run:
        print("Restart Claude Code (or run /agents) so the new agents are loaded.")


if __name__ == "__main__":
    main()
