#!/usr/bin/env python3
"""Quality gates for the model orchestrator.

Runs the project's checks (lint, types, tests, build, smoke test) in order and
records which exact state of the code passed. A push is allowed only when the
commit being pushed matches a state that passed.

    python3 gate.py --plan .orchestrator/plans/x.md   run the gates
    python3 gate.py --status                          show the last result
    python3 gate.py --clear                           forget the last result
    python3 gate.py --hook                            PreToolUse hook mode (reads JSON on stdin)

Gates come from "gates" in model-orchestrator.json; if that is empty, from the
"## Gates" section of the plan file, one per line:  - name: `command`

Standard library only.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mo_config import load_config

GATE_LINE = re.compile(r"^\s*[-*]\s*\**([^:`*]+?)\**\s*:\s*`(.+)`\s*$")
PUSH = re.compile(r"\bgit\s+(?:-{1,2}[^\s]+\s+(?:[^\s-][^\s]*\s+)?)*push\b")
EXCLUDE = ":(exclude,top).orchestrator"


def git(*args, cwd=None, env=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r


def repo_root(cwd=None):
    r = git("rev-parse", "--show-toplevel", cwd=cwd, check=False)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def state_path(root):
    git_dir = git("rev-parse", "--absolute-git-dir", cwd=root).stdout.strip()
    return Path(git_dir) / "model-orchestrator" / "gate.json"


def worktree_tree(root):
    """Tree hash of the working tree as it would be committed (respects .gitignore)."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
        if git("rev-parse", "--verify", "-q", "HEAD", cwd=root, check=False).returncode == 0:
            git("read-tree", "HEAD", cwd=root, env=env)
        git("add", "-A", cwd=root, env=env)
        return git("write-tree", cwd=root, env=env).stdout.strip()


def same_code(root, tree, rev="HEAD"):
    """True when rev holds the same files as tree, ignoring .orchestrator/."""
    r = git("diff", "--quiet", tree, rev, "--", ".", EXCLUDE, cwd=root, check=False)
    return r.returncode == 0


def read_state(root):
    path = state_path(root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"status": "unreadable"}


def gates_from_plan(plan):
    gates, inside = [], False
    for line in Path(plan).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "gates"
            continue
        m = GATE_LINE.match(line) if inside else None
        if m:
            gates.append({"name": m.group(1).strip(), "command": m.group(2).strip()})
    return gates


def run_gates(args, root):
    config, _ = load_config(root)
    gates = [g for g in (config.get("gates") or [])
             if isinstance(g, dict) and g.get("name") and g.get("command")]
    source = "config"
    if not gates and args.plan:
        gates, source = gates_from_plan(args.plan), f"plan {args.plan}"
    if not gates:
        sys.exit("error: no gates defined. Add \"gates\" to .claude/model-orchestrator.json "
                 "or a \"## Gates\" section to the plan (- name: `command`). "
                 "A gate run with nothing to check does not count as a pass.")

    print(f"Gates from {source}:")
    results, failed = [], False
    for gate in gates:
        if failed and not args.keep_going:
            results.append({"name": gate["name"], "status": "skipped"})
            print(f"SKIP  {gate['name']}")
            continue
        start = time.time()
        try:
            r = subprocess.run(gate["command"], shell=True, cwd=root, capture_output=True,
                               text=True, timeout=args.timeout, stdin=subprocess.DEVNULL)
            code, output = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            code, output = 124, f"[timed out after {args.timeout}s]"
        seconds = round(time.time() - start, 1)
        ok = code == 0
        failed = failed or not ok
        results.append({"name": gate["name"], "command": gate["command"],
                        "status": "pass" if ok else "fail", "exit": code, "seconds": seconds})
        print(f"{'PASS' if ok else 'FAIL'}  {gate['name']}  ({seconds}s)  $ {gate['command']}")
        if not ok:
            output = output.strip()
            if len(output) > args.tail:
                output = "[...]\n" + output[-args.tail:]
            print(f"--- output of {gate['name']} (exit {code}) ---\n{output}\n---")

    # Fingerprint after the run, so files a formatter rewrote are included.
    state = {"status": "fail" if failed else "pass", "tree": worktree_tree(root),
             "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "gates": results}
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    if failed:
        print("RESULT: FAIL. Fix the cause and run the gates again; do not push.")
        sys.exit(1)
    print("RESULT: PASS. Commit this exact state; any further edit needs a new gate run before a push.")


def push_verdict(root):
    """Return (allowed, message) for pushing HEAD."""
    state = read_state(root)
    if state is None:
        return True, "no gate run recorded in this repository"
    if state.get("status") != "pass":
        return False, f"the last gate run ended with status {state.get('status')!r}"
    if git("rev-parse", "--verify", "-q", "HEAD", cwd=root, check=False).returncode != 0:
        return True, "no commits yet"
    if not same_code(root, state["tree"]):
        return False, "the code in HEAD differs from the code that passed the gates"
    return True, "HEAD matches the code that passed the gates"


def hook():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    command = (event.get("tool_input") or {}).get("command") or ""
    if event.get("tool_name") != "Bash" or not PUSH.search(command):
        return
    root = repo_root(event.get("cwd") or None)
    if root is None:
        return
    try:
        allowed, why = push_verdict(root)
    except Exception:  # a broken check must not block unrelated work
        return
    if not allowed:
        print(f"Push blocked by the model orchestrator: {why}. Run the quality gates "
              f"(python3 {Path(__file__).resolve()} --plan <plan file>), commit the state "
              "that passed, then push. Do not clear the gate record yourself; only the user "
              "may decide to push without passing gates.", file=sys.stderr)
        sys.exit(2)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--plan", help="plan file whose '## Gates' section lists the gates")
    p.add_argument("--keep-going", action="store_true", help="run later gates after a failure")
    p.add_argument("--timeout", type=int, default=1800, help="seconds per gate (default 1800)")
    p.add_argument("--tail", type=int, default=3000, help="characters of failing output to print")
    p.add_argument("--status", action="store_true", help="show the last result and whether HEAD may be pushed")
    p.add_argument("--clear", action="store_true", help="forget the last result (pushes are no longer checked)")
    p.add_argument("--hook", action="store_true", help="PreToolUse hook mode")
    args = p.parse_args()

    if args.hook:
        return hook()
    root = repo_root()
    if root is None:
        sys.exit("error: not inside a git repository")
    if args.clear:
        state_path(root).unlink(missing_ok=True)
        print("Gate record cleared.")
        return
    if args.status:
        state = read_state(root)
        allowed, why = push_verdict(root)
        print(json.dumps({"last_run": state, "push_allowed": allowed, "reason": why}, indent=2))
        return
    run_gates(args, root)


if __name__ == "__main__":
    main()
