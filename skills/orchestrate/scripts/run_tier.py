#!/usr/bin/env python3
"""Run one orchestrator task on an external (non-Claude) coding agent CLI.

A role whose configured value is {"command": "..."} is executed by that
command instead of a Claude subagent. This script builds the prompt (role
instructions plus the task brief), runs the command without a shell, and
prints the exit code and the tail of the output.

    python3 run_tier.py --show
    python3 run_tier.py --role builder --brief "Plan: .tierwise/plans/x.md. Do task T2."
    python3 run_tier.py --role runner --brief-file brief.md --timeout 3600

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

from tw_config import ROLE_TIER, SKILL_DIR, agent_name, load_config, resolve


def role_text(role):
    text = (SKILL_DIR / "agents" / f"{agent_name(role)}.md").read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2].strip() if len(parts) == 3 and not parts[0].strip() else text.strip()


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--show", action="store_true", help="print how every role resolves, as JSON")
    p.add_argument("--role", choices=list(ROLE_TIER))
    p.add_argument("--brief", help="task brief text")
    p.add_argument("--brief-file", help="file holding the task brief")
    p.add_argument("--timeout", type=int, default=1800, help="seconds (default 1800)")
    p.add_argument("--tail", type=int, default=4000, help="characters of output to print (default 4000)")
    args = p.parse_args()

    config, config_path = load_config()
    roles = resolve(config)

    if args.show:
        print(json.dumps({"config": str(config_path) if config_path else None,
                          "roles": roles, "gates": config.get("gates") or []}, indent=2))
        return

    if not args.role:
        p.error("--role is required unless --show is given")
    if bool(args.brief) == bool(args.brief_file):
        p.error("give exactly one of --brief or --brief-file")
    entry = roles[args.role]
    if entry["kind"] != "command":
        sys.exit(f"error: role {args.role} runs on the Claude model {entry['value']!r}; "
                 "spawn its subagent instead of running this script")

    brief = args.brief or Path(args.brief_file).read_text(encoding="utf-8")
    prompt = f"{role_text(args.role)}\n\n## Your task\n\n{brief.strip()}\n"

    try:
        argv = shlex.split(entry["value"])
    except ValueError as e:
        sys.exit(f"error: cannot parse the command for role {args.role}: {e}")
    if not argv:
        sys.exit(f"error: the command for role {args.role} is empty")

    prompt_file = None
    stdin_text = None
    try:
        if any("{prompt_file}" in a for a in argv):
            with tempfile.NamedTemporaryFile("w", suffix=".md", prefix="tw-brief-",
                                             delete=False, encoding="utf-8") as f:
                f.write(prompt)
                prompt_file = f.name
        if not any("{prompt}" in a or "{prompt_file}" in a for a in argv):
            stdin_text = prompt
        argv = [a.replace("{prompt_file}", prompt_file or "").replace("{prompt}", prompt)
                for a in argv]

        kwargs = {"input": stdin_text} if stdin_text is not None else {"stdin": subprocess.DEVNULL}
        try:
            result = subprocess.run(argv, capture_output=True, text=True,
                                    timeout=args.timeout, **kwargs)
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
    print(f"ROLE: {args.role}\nEXIT: {code}\nOUTPUT:\n{output}")
    sys.exit(0 if code == 0 else 1)


if __name__ == "__main__":
    main()
