# Configuration

## Config file

The skill reads the first file that exists:

1. `.claude/model-orchestrator.json` in the project
2. `~/.claude/model-orchestrator.json`

```json
{
  "allowFable": false,
  "tiers": {
    "top": "opus",
    "mid": "sonnet",
    "small": "haiku"
  }
}
```

| Key | Meaning |
|---|---|
| `allowFable` | When true and `tiers.top` is not set, the top tier uses `fable`. Off by default, because Fable costs more and not every account has it. |
| `tiers.top` / `tiers.mid` / `tiers.small` | The model for each tier. An alias (`fable`, `opus`, `sonnet`, `haiku`) or any model ID that `claude --model` accepts, including models served through your own gateway. Any key may be omitted. |

Defaults with no file: `opus` / `sonnet` / `haiku`.

## Setup script

`scripts/setup.py` writes the config file and generates the three agents (`mo-architect`, `mo-builder`, `mo-runner`) with the chosen models pinned in their frontmatter. It needs only Python 3.

```bash
# Defaults (opus / sonnet / haiku) for this project
python3 scripts/setup.py

# Let the planner use Fable
python3 scripts/setup.py --allow-fable

# Custom models, for every project of this user
python3 scripts/setup.py --scope user --top claude-opus-5-5 --mid claude-sonnet-5-5 --small claude-haiku-5-5

# Show what would be written
python3 scripts/setup.py --allow-fable --dry-run
```

| Flag | Effect |
|---|---|
| `--scope project` (default) | Writes to `./.claude/` |
| `--scope user` | Writes to `~/.claude/` |
| `--top`, `--mid`, `--small` | Model for the tier |
| `--allow-fable` | Sets `allowFable` and, unless `--top` is given, plans with `fable` |
| `--dry-run` | Prints the result and writes nothing |

## When setup is required

- **Aliases only**: setup is optional. The skill passes the alias when it spawns each agent.
- **Any other model ID**: run setup. A per-spawn model override accepts only aliases, so a full or custom ID has to live in the agent file, which is what the script generates.

Project and user agents take priority over the ones shipped in the plugin, so generated agents are used automatically.

## One-off overrides

Say it in the request: "orchestrate this, plan with fable" or "use opus for the build this time". That applies to the current run only and does not change the file.
