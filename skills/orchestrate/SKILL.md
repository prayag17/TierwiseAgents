---
name: orchestrate
description: Route work to the cheapest model tier that can do it well, to cut token cost. A top-tier model plans, a mid-tier model implements the written plan, and a small model handles mechanical chores such as renames, file moves, formatting and boilerplate. Use when the user asks to plan and build a feature, hands over multi-step or multi-file work, asks to save tokens or cost, or types /orchestrate. Skip for a single small edit or a quick question.
argument-hint: "[task description]"
---

# Model Orchestrator

You are the router. Your job is to spend expensive tokens only where they change the outcome: on decisions. Everything that is "follow these instructions" goes to a cheaper model. Keep your own context light: delegate reading, planning and editing rather than doing them yourself, and never re-read what a subagent already summarized.

Task: $ARGUMENTS

## 1. Resolve the tier models

Read the first config file that exists:

1. `.claude/model-orchestrator.json` (project)
2. `~/.claude/model-orchestrator.json` (user)

```json
{
  "allowFable": false,
  "tiers": { "top": "opus", "mid": "sonnet", "small": "haiku" }
}
```

Resolve each tier in this order:

- A value in `tiers` wins.
- Otherwise `top` is `fable` when `allowFable` is true, else `opus`; `mid` is `sonnet`; `small` is `haiku`.
- With no config file at all, use `opus` / `sonnet` / `haiku`.
- An instruction from the user in this conversation ("use fable for planning", "build with opus") overrides the file for this run. Never pick `fable` unless the config or the user allowed it.

A tier value is either an alias (`fable`, `opus`, `sonnet`, `haiku`) or any other model ID (a full Claude ID, or a model served through the user's gateway). The Agent tool's `model` parameter accepts only aliases, so:

- Alias: pass it as `model` when spawning the tier's agent.
- Any other ID: it must be pinned in an agent file. Check that `.claude/agents/mo-<role>.md` or `~/.claude/agents/mo-<role>.md` exists with that model, then spawn it without a `model` parameter. If it is missing, tell the user to run `python3 scripts/setup.py` from this skill's directory (see `references/configuration.md`) and fall back to the default alias for that tier meanwhile.

## 2. Pick the agent for each tier

| Tier | Role | Agent |
|---|---|---|
| top | plan, design, diagnose | `mo-architect` |
| mid | implement a written plan | `mo-builder` |
| small | mechanical chores | `mo-runner` |

Use the first that is available: the project or user agent `mo-<role>`, then the plugin agent `model-orchestrator:mo-<role>`. If neither exists (skill installed standalone, no setup run), spawn `general-purpose` with the tier's `model` alias and paste the body of `agents/mo-<role>.md` from this skill's directory at the top of the prompt.

## 3. Triage the task

Classify before spending anything. Pick the lowest row that fits.

| The task is | Route |
|---|---|
| A question, or an edit you can finish in under about 20 lines in one file | Do it yourself. A cold subagent costs more than the edit. |
| Purely mechanical: rename, move or reorganize files, reformat, bulk find and replace, boilerplate from a pattern, updating imports | `small` directly, no plan |
| Implementation with a clear spec already given (the user wrote the steps, or a plan file exists) | `mid` directly |
| A feature, a refactor with design choices, anything ambiguous, cross-cutting or risky, or a bug with an unknown cause | `top` plans, then `mid` and `small` execute |

When unsure between two tiers, start with the cheaper one: escalation is cheap, over-provisioning is not.

## 4. Plan (top tier)

Spawn the architect with the user's request verbatim, any constraints from the conversation, and the plan path `.orchestrator/plans/<short-slug>.md`. The architect explores the codebase and writes the plan file in the format of `references/plan-format.md`: self-contained tasks, each tagged with a tier, exact files, steps and an acceptance check.

The architect returns only a short summary. Show the user the task list (id, tier, one line each) and the plan path, then ask for a go-ahead before building, unless they already said to proceed without asking. This checkpoint is the cheapest place to catch a wrong direction.

## 5. Execute (mid and small tiers)

For each task, in dependency order:

- Spawn the agent for the task's tier with a brief that holds only the plan path, the task id, and "read the plan, do this task, run its acceptance check". Do not paste the plan or code into the brief: the agent reads the file itself.
- Tasks the plan marks as parallel and that touch different files go out in one message as parallel spawns.
- Each agent ends with a report of `STATUS: DONE | FAILED | BLOCKED`, files changed, and the acceptance check output. Trust the report; do not re-read the diff.

## 6. Verify and escalate

- `DONE` with a passing check: mark the task done in the plan file and move on.
- `FAILED` or `BLOCKED`, or a check that does not pass: escalate that task one tier (`small` → `mid` → `top`), passing the previous agent's report so the next one does not repeat it. Do not retry at the same tier.
- If the `top` tier also fails, or a blocker says the plan itself is wrong, stop and bring it to the user with the evidence.
- After the last task, run the plan's final check (full test suite, build or lint, as the plan names it) once.

## 7. Report

Finish with a short table: task, tier and model that ran it, result, and any escalation. Add one line on what was verified and anything left undone.

## Rules that protect the savings

- Never delegate upward by default. A task goes to `top` only through triage or escalation.
- Never have two tiers do the same reading. The plan file is the only handoff.
- Never let a subagent spawn further subagents.
- The session you run in is billed too. If the user's session is on a top-tier model and most work is being delegated, mention once that `/model sonnet` for the session itself would save more.
