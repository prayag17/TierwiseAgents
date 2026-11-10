# Model Orchestrator

A Claude Code skill that sends each piece of work to the cheapest model that can do it well.

| Tier | Agent | Default model | Does |
|---|---|---|---|
| Top | `mo-architect` | `opus` (or `fable` if you allow it) | Plans features, makes design decisions, diagnoses hard bugs |
| Mid | `mo-builder` | `sonnet` | Implements the written plan, writes tests |
| Small | `mo-runner` | `haiku` | Renames, file moves, formatting, find and replace, boilerplate |

## How it works

1. **Triage.** Small edits are done inline, mechanical chores go straight to the small model, clearly specified work goes straight to the mid model. Only real design work reaches the top model.
2. **Plan.** The architect explores the code and writes a self-contained plan to `.orchestrator/plans/<slug>.md`. Every task is tagged with a tier and has an acceptance check. You approve the task list before anything is built.
3. **Execute.** Each task is handed to its tier with nothing but the plan path and task id. Independent tasks run in parallel.
4. **Verify and escalate.** A task that fails its check or reports a blocker moves up one tier (small → mid → top). Nothing is retried at the same tier.
5. **Report.** You get a table of which model ran what, and any escalations.

## Install

### As a plugin (recommended)

```
/plugin marketplace add prayag17/ModelOrchestrator
/plugin install model-orchestrator@prayag17
```

Then run `/model-orchestrator:orchestrate <task>`, or just describe a multi-step feature and the skill activates on its own.

### As a standalone skill

```bash
git clone https://github.com/prayag17/ModelOrchestrator
cp -r ModelOrchestrator/skills/orchestrate ~/.claude/skills/orchestrate   # or .claude/skills/ in a project
python3 ~/.claude/skills/orchestrate/scripts/setup.py --scope user         # optional: installs the three agents
```

Then run `/orchestrate <task>`. Without the setup step the skill still works, using general-purpose subagents with the tier models.

## Choosing models

Defaults are `opus` / `sonnet` / `haiku`. To change them, run the setup script from the skill folder:

```bash
python3 scripts/setup.py --allow-fable                 # plan with Fable
python3 scripts/setup.py --top claude-opus-5-5 --mid claude-sonnet-5-5 --small claude-haiku-5-5
python3 scripts/setup.py --scope user                  # apply to all your projects
```

or write `.claude/model-orchestrator.json` yourself:

```json
{
  "allowFable": true,
  "tiers": { "mid": "sonnet", "small": "haiku" }
}
```

Fable is never used unless `allowFable` is set or you ask for it in the request. Any model ID that `claude --model` accepts works, including models behind your own gateway. See [configuration](skills/orchestrate/references/configuration.md) for details.

For a single run, just say so: "orchestrate this, plan with fable".

## Getting the most out of it

- The session you type in is billed too. Since the planning is delegated, running the session itself on a mid-tier model (`/model sonnet`) saves the most.
- Add `.orchestrator/` to your project's `.gitignore`, or commit the plans if you want a record.
- The skill deliberately skips delegation for tiny edits: starting a cold subagent costs more than the edit.

## Layout

```
.claude-plugin/          plugin and marketplace manifests
skills/orchestrate/
  SKILL.md               the router
  agents/                mo-architect, mo-builder, mo-runner
  references/            plan format, configuration
  scripts/setup.py       writes config and pins models into the agents
```

## License

MIT
