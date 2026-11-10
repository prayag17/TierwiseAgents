#!/usr/bin/env python3
"""Run one orchestrator task on an external (non-Claude) coding agent CLI.

A tier whose config value is {"command": "..."} is executed by that command
instead of a Claude subagent. This script builds the prompt (role instructions
plus the task brief), runs the command without a shell, and prints the exit
code and the tail of the output.

    python3 run_tier.py --show
    python3 run_tier.py --tier small --brief "Plan: .orchestrator/plans/x.md. Do task T2."
    python3 run_tier.py --tier mid --brief-file brief.md --timeout 3600

Placeholders in the command:
    {prompt}       replaced by the full prompt text (one argument)
    {prompt_file}  replaced by the path of a file holding the prompt
With neither placeholder, the prompt is sent on standard input.

Standard library only.
"""

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULTS = {"top": "opus", "mid": "sonnet", "small": "haiku"}
ROLES = {"top": "mo-architect", "mid": "mo-builder", "small": "mo-runner"}
ALIASES = {"fable", "opus", "sonnet", "haiku"}
SKILL_DIR = Path(__file__).resolve().parent.parent


def load_config():
    for base in (Path.cwd(), Path.home()):
        path = base / ".claude" / "model-orchestrator.json"
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8")), path
            except json.JSONDecodeError as e:
                sys.exit(f"error: {path} is not valid JSON: {e}")
    return {}, None


def resolve(config):
    """Return {tier: {"kind": alias|model|command, "value": str}}."""
    tiers = dict(DEFAULTS)
    if config.get("allowFable"):
        tiers["top"] = "fable"
    tiers.update({k: v for k, v in (config.get("tiers") or {}).items() if k in DEFAULTS})

    out = {}
    for tier, value in tiers.items():
        if isinstance(value, dict):
            command = value.get("command")
            if not isinstance(command, str) or not command.strip():
                sys.exit(f"error: tiers.{tier} needs a non-empty \"command\" string")
            out[tier] = {"kind": "command", "value": command}
        elif isinstance(value, str) and value.strip():
            kind = "alias" if value in ALIASES else "model"
            out[tier] = {"kind": kind, "value": value}
        else:
            sys.exit(f"error: tiers.{tier} must be a model name or {{\"command\": ...}}")
    if out["top"]["value"] == "fable" and not config.get("allowFable"):
        out["top"] = {"kind": "alias", "value": DEFAULTS["top"]}
    return out


def role_text(tier):
    path = SKILL_DIR / "agents" / f"{ROLES[tier]}.md"
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) == 3 and not parts[0].strip() else text.strip()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--show", action="store_true", help="print the resolved tiers as JSON and exit")
    p.add_argument("--tier", choices=list(DEFAULTS))
    p.add_argument("--brief", help="task brief text")
    p.add_argument("--brief-file", help="file holding the task brief")
    p.add_argument("--timeout", type=int, default=1800, help="seconds (default 1800)")
    p.add_argument("--tail", type=int, default=4000, help="characters of output to print (default 4000)")
    args = p.parse_args()

    config, config_path = load_config()
    tiers = resolve(config)

    if args.show:
        print(json.dumps({"config": str(config_path) if config_path else None, "tiers": tiers}, indent=2))
        return

    if not args.tier:
        p.error("--tier is required unless --show is given")
    if bool(args.brief) == bool(args.brief_file):
        p.error("give exactly one of --brief or --brief-file")
    tier = tiers[args.tier]
    if tier["kind"] != "command":
        sys.exit(f"error: tier {args.tier} is the Claude model {tier['value']!r}; "
                 "spawn its subagent instead of running this script")

    brief = args.brief or Path(args.brief_file).read_text(encoding="utf-8")
    prompt = f"{role_text(args.tier)}\n\n## Your task\n\n{brief.strip()}\n"

    try:
        argv = shlex.split(tier["value"])
    except ValueError as e:
        sys.exit(f"error: cannot parse the command for tier {args.tier}: {e}")
    if not argv:
        sys.exit(f"error: the command for tier {args.tier} is empty")

    prompt_file = None
    stdin_text = None
    try:
        if any("{prompt_file}" in a for a in argv):
            with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="mo-brief-",
                                             delete=False, encoding="utf-8") as f:
                f.write(prompt)
                prompt_file = f.name
        if not any("{prompt}" in a or "{prompt_file}" in a for a in argv):
            stdin_text = prompt
        argv = [a.replace("{prompt_file}", prompt_file or "").replace("{prompt}", prompt)
                for a in argv]

        try:
            result = subprocess.run(argv, input=stdin_text, capture_output=True, text=True,
                                    timeout=args.timeout,
                                    stdin=None if stdin_text is not None else subprocess.DEVNULL)
            code, output = result.returncode, (result.stdout or "") + (result.stderr or "")
        except FileNotFoundError:
            sys.exit(f"error: command not found: {argv[0]}")
        except subprocess.TimeoutExpired as e:
            def text(x):
                return x.decode("utf-8", "replace") if isinstance(x, bytes) else (x or "")
            code, output = 124, text(e.stdout) + text(e.stderr) + f"\n[timed out after {args.timeout}s]"
    finally:
        if prompt_file:
            Path(prompt_file).unlink(missing_ok=True)

    output = output.strip()
    if len(output) > args.tail:
        output = "[...]\n" + output[-args.tail:]
    print(f"TIER: {args.tier}\nEXIT: {code}\nOUTPUT:\n{output}")
    sys.exit(0 if code == 0 else 1)


if __name__ == "__main__":
    main()
