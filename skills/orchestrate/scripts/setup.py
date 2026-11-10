#!/usr/bin/env python3
"""Configure the model orchestrator.

Writes model-orchestrator.json and generates the mo-architect, mo-builder and
mo-runner agents with the chosen models pinned in their frontmatter.
Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULTS = {"top": "opus", "mid": "sonnet", "small": "haiku"}
ROLES = {"top": "mo-architect", "mid": "mo-builder", "small": "mo-runner"}
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\[\]@-]*$")

TEMPLATES = Path(__file__).resolve().parent.parent / "agents"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scope", choices=["project", "user"], default="project",
                   help="write to ./.claude (project) or ~/.claude (user)")
    p.add_argument("--top", help="model for planning (default: opus, or fable with --allow-fable)")
    p.add_argument("--mid", help="model for implementation (default: sonnet)")
    p.add_argument("--small", help="model for mechanical chores (default: haiku)")
    p.add_argument("--allow-fable", action="store_true",
                   help="allow Fable; plans with it unless --top is given")
    p.add_argument("--dry-run", action="store_true", help="print the result, write nothing")
    return p.parse_args()


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

    tiers = dict(DEFAULTS)
    if args.allow_fable:
        tiers["top"] = "fable"
    for tier in DEFAULTS:
        value = getattr(args, tier)
        if value:
            tiers[tier] = value.strip()
    for tier, model in tiers.items():
        if not MODEL_ID.match(model):
            sys.exit(f"error: --{tier} {model!r} is not a valid model name")
    if "fable" in tiers.values() and not args.allow_fable:
        sys.exit("error: a tier is set to fable; pass --allow-fable to confirm")

    base = (Path.home() if args.scope == "user" else Path.cwd()) / ".claude"
    config_path = base / "model-orchestrator.json"
    config = {"allowFable": args.allow_fable, "tiers": tiers}

    outputs = {config_path: json.dumps(config, indent=2) + "\n"}
    for tier, role in ROLES.items():
        template = TEMPLATES / f"{role}.md"
        if not template.is_file():
            sys.exit(f"error: missing agent template {template}")
        outputs[base / "agents" / f"{role}.md"] = pin_model(
            template.read_text(encoding="utf-8"), tiers[tier])

    for tier, role in ROLES.items():
        print(f"{tier:<5} {role:<13} -> {tiers[tier]}")
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
