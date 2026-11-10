# Configuration

## Config file

The skill reads the first file that exists:

1. `.claude/tierwise.json` in the project
2. `~/.claude/tierwise.json`

```json
{
  "allowFable": false,
  "tiers": { "top": "opus", "mid": "sonnet", "small": "haiku" },
  "roles": { "reviewer": "opus" },
  "gates": [
    { "name": "lint", "command": "npm run lint" },
    { "name": "test", "command": "npm test" },
    { "name": "build", "command": "npm run build" }
  ]
}
```

Every key is optional.

| Key | Meaning |
|---|---|
| `allowFable` | When true, the top tier uses `fable` unless `tiers.top` says otherwise. Off by default, because Fable costs more and not every account has it. Fable is never used while this is false. |
| `tiers.top` / `tiers.mid` / `tiers.small` | What runs each tier. One of: a Claude alias (`fable`, `opus`, `sonnet`, `haiku`); any other model ID that `claude --model` accepts; or `{"command": "..."}` to run the tier on an external CLI (see "Non-Claude models"). |
| `roles.<role>` | Overrides the tier for one role, in the same three forms. |
| `gates` | The checks that must pass before a push, run in order. When present, they replace the gates the architect writes into a plan. |

Roles and their tiers:

| Tier | Roles |
|---|---|
| top | `architect` |
| mid | `builder`, `tester`, `reviewer`, `debugger` |
| small | `scout`, `runner` |

Defaults with no file: `opus` / `sonnet` / `haiku`.

## Setup script

`scripts/setup.py` writes the config file and generates the seven `tw-*` agents with the chosen models pinned in their frontmatter. It needs only Python 3. Running it again adds to the existing file in that scope.

```bash
# Defaults (opus / sonnet / haiku) for this project
python3 scripts/setup.py

# Let the planner use Fable
python3 scripts/setup.py --allow-fable

# Custom models, for every project of this user
python3 scripts/setup.py --scope user --top claude-opus-5-5 --mid claude-sonnet-5-5 --small claude-haiku-5-5

# One role on a stronger model, and project-wide gates
python3 scripts/setup.py --role reviewer=opus --gate lint='npm run lint' --gate test='npm test'

# Show what would be written
python3 scripts/setup.py --allow-fable --dry-run
```

| Flag | Effect |
|---|---|
| `--scope project` (default) | Writes to `./.claude/` |
| `--scope user` | Writes to `~/.claude/` |
| `--top`, `--mid`, `--small` | Model for the tier |
| `--top-cmd`, `--mid-cmd`, `--small-cmd` | Run the tier on an external command instead of a Claude model |
| `--role ROLE=MODEL` | Override one role (repeatable) |
| `--gate NAME=COMMAND` | Define the gates, in order (repeatable; replaces the existing list) |
| `--allow-fable` | Sets `allowFable` and, unless `--top` is given, plans with `fable` |
| `--dry-run` | Prints the result and writes nothing |

## When setup is required

- **Aliases only**: setup is optional. The skill passes the alias when it spawns each agent.
- **External command**: no agent file is needed; the config entry is enough.
- **Any other model ID**: run setup. A per-spawn model override accepts only aliases, so a full or custom ID has to live in the agent file, which is what the script generates.

Project and user agents take priority over the ones shipped in the plugin, so generated agents are used automatically.

## Non-Claude models

There are two ways to put a non-Claude model on a tier. They can be mixed: for example Claude plans, and another vendor's model builds.

### 1. External command (recommended)

Set the tier to a command that runs another coding agent CLI non-interactively. The orchestrator writes the same brief it would give a Claude subagent, and `scripts/run_tier.py` runs your command with it.

```json
{
  "tiers": {
    "top": "opus",
    "mid": { "command": "codex exec --full-auto -m <model> {prompt}" },
    "small": { "command": "gemini --yolo -m <model> -p {prompt}" }
  }
}
```

or with the setup script:

```bash
python3 scripts/setup.py --mid-cmd 'codex exec --full-auto -m <model> {prompt}'
```

Placeholders:

| Placeholder | Replaced by |
|---|---|
| `{prompt}` | The full prompt (role instructions plus the task brief), passed as one argument |
| `{prompt_file}` | The path of a temporary file holding the prompt |
| neither | The prompt is sent on standard input |

Command shapes for common tools. Flags change between versions, so confirm them with the tool's `--help`:

| Tool | Command |
|---|---|
| OpenAI Codex CLI | `codex exec --full-auto -m <model> {prompt}` |
| Gemini CLI | `gemini --yolo -m <model> -p {prompt}` |
| opencode (any provider, including local models) | `opencode run -m <provider/model> {prompt}` |
| aider | `aider --yes --model <model> --message-file {prompt_file}` |
| Your own script | `./scripts/my-agent.sh {prompt_file}` |

How it behaves:

- The command runs in the project directory, without a shell, so the prompt cannot be interpreted as shell syntax. Pipes and `&&` are not available in the command; wrap them in a script if you need them.
- The tool must be able to edit files and run commands without asking, which is what flags such as `--full-auto`, `--yolo` and `--yes` do. That gives the tool unattended write access to your working tree, so use it in a repository under version control.
- The tool must already be installed and signed in. The orchestrator does not handle its credentials.
- Because other tools do not follow the report format reliably, the orchestrator runs each task's acceptance check itself. A non-zero exit or a failing check escalates the task one tier, exactly as with Claude tiers.
- The default time limit is 30 minutes per task (`--timeout` on `run_tier.py`).

Test a command before relying on it:

```bash
python3 scripts/run_tier.py --show                       # what each role resolves to
python3 scripts/run_tier.py --role runner --brief "Reply with the word ready and change nothing."
```

### 2. A gateway that serves other models to Claude Code

If your Claude Code already talks to a gateway (`ANTHROPIC_BASE_URL`) that exposes other models under their own IDs, put those IDs in `tiers` and run setup so they are pinned in the agent files:

```bash
python3 scripts/setup.py --mid <gateway-model-id> --small <gateway-model-id>
```

Be aware that Anthropic does not support routing Claude Code to non-Claude models through a gateway. It can work, but subagent features such as tool use and effort levels depend on how well the gateway and the model emulate the Claude API. Prefer the external command route unless you already run such a setup.

## Quality gates

`scripts/gate.py` runs the gates and records which exact state of the code passed.

```bash
python3 scripts/gate.py --plan .tierwise/plans/<slug>.md   # run them
python3 scripts/gate.py --status                               # last result, and whether HEAD may be pushed
python3 scripts/gate.py --clear                                # forget the last result
```

- Gates come from `gates` in the config file; if that is empty, from the `## Gates` section of the plan.
- They run in order through your shell, from the repository root, and stop at the first failure (`--keep-going` runs the rest). Each has a 30 minute limit (`--timeout`).
- A run with no gates defined is an error, not a pass.
- The result is stored inside `.git/`, so it is never committed and does not change your working tree.

### The push guard

With the plugin installed, a hook checks every `git push` that Claude runs:

| Situation | Push |
|---|---|
| No gate run has ever been recorded in this repository | Allowed. The guard only applies once you use gates. |
| The last gate run failed | Blocked |
| The last run passed, but `HEAD` holds different code than the code that passed | Blocked |
| The last run passed and `HEAD` matches it | Allowed |

Changes under `.tierwise/` are ignored in the comparison. To stop the guard for a repository, run `gate.py --clear` yourself; the skill tells Claude not to do that on its own.

Limits to know about:

- The guard covers pushes made by Claude inside Claude Code. It does not stop a push you type in your own terminal, and it does not see deploy commands. Protect production branches on your Git host as well.
- It compares against `HEAD`, so it assumes you push the branch you are on.
- As a standalone skill there is no hook; the skill's instructions still require a passing gate run before any push.

## One-off overrides

Say it in the request: "orchestrate this, plan with fable" or "use opus for the build this time". That applies to the current run only and does not change the file.
