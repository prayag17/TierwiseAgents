---
name: orchestrate
description: Route development work to the cheapest model that can do it well, and gate it with tests and review before it is pushed. A top-tier model plans; mid-tier models write tests, implement, debug and review; a small model scouts the codebase and handles mechanical chores such as renames, file moves and formatting. Use when the user asks to plan and build a feature, hands over multi-step or multi-file work, wants changes tested before pushing, asks to save tokens or cost, or types /orchestrate. Skip for a single small edit or a quick question.
argument-hint: "[task description]"
---

# Model Orchestrator

You are the router. Spend expensive tokens only where they change the outcome: on decisions. Everything that is "follow these instructions" goes to a cheaper model, and nothing is pushed until the code has passed its gates. Keep your own context light: delegate reading, planning, editing and debugging, and never re-read what a subagent already summarized.

Task: $ARGUMENTS

## Roles

| Role | Agent | Tier | Does |
|---|---|---|---|
| scout | `mo-scout` | small | Read-only map of the relevant code, conventions and check commands |
| architect | `mo-architect` | top | Decisions and the plan file; last stop for escalations |
| tester | `mo-tester` | mid | Tests written from the plan before the code exists |
| builder | `mo-builder` | mid | Implements one planned task |
| runner | `mo-runner` | small | Mechanical chores |
| debugger | `mo-debugger` | mid | Root cause and minimal fix for a failing check |
| reviewer | `mo-reviewer` | mid | Read-only review of the final diff against the plan |

Scripts and references named below are in this skill's directory.

## 1. Resolve models

Run `python3 scripts/run_tier.py --show`. It reads `.claude/model-orchestrator.json` (project) or `~/.claude/model-orchestrator.json` (user) and prints, for each role, a `kind` and a `value`:

| Kind | Meaning | How to run the role |
|---|---|---|
| `alias` | `fable`, `opus`, `sonnet` or `haiku` | Spawn the role's agent and pass the alias as `model`. |
| `model` | Any other model ID | The Agent tool's `model` parameter accepts only aliases, so the ID must be pinned in `.claude/agents/mo-<role>.md` or `~/.claude/agents/mo-<role>.md`. Spawn that agent without a `model` parameter. If the file is missing, tell the user to run `scripts/setup.py` and use the tier's default alias meanwhile. |
| `command` | An external, non-Claude coding agent CLI | `python3 scripts/run_tier.py --role <role> --brief "<brief>"` through Bash. |

Defaults are `opus` (top), `sonnet` (mid), `haiku` (small). The script never returns `fable` unless the config allows it. An instruction from the user in this conversation ("plan with fable", "review with opus") overrides the file for this run; do not choose `fable` on your own.

For an agent, use the first available: the project or user agent `mo-<role>`, then the plugin agent `model-orchestrator:mo-<role>`. If neither exists, spawn `general-purpose` with the role's alias and paste the body of `agents/mo-<role>.md` at the top of the prompt.

Details, including non-Claude models: `references/configuration.md`.

## 2. Triage

Classify before spending anything, and pick the lowest row that fits. The size of the cycle follows the size of the task.

| The task is | Cycle |
|---|---|
| A question, or an edit under about 20 lines in one file | Do it yourself. A cold subagent costs more than the edit. Run the gates before any push if the project has them configured. |
| Purely mechanical: rename, move or reorganize files, reformat, bulk replace, boilerplate from a pattern | runner → gates |
| Implementation with a clear spec already given | builder (writes its own tests) → gates → reviewer |
| A bug with an unknown cause | debugger (adds a regression test first) → gates → reviewer |
| A feature, a refactor with design choices, anything ambiguous, cross-cutting or risky | Full cycle, sections 3 to 8 |

When unsure between two rows, start with the cheaper one: escalation is cheap, over-provisioning is not.

## 3. Scout (small)

Before planning in a codebase that has not been mapped for this request, spawn the scout with the request and the path `.orchestrator/context/<slug>.md`. It records the relevant files, conventions, test setup, check commands and which checks pass right now. Skip the scout for a tiny or empty repository, or when a context file for this area already exists.

A check that already fails before any change is a baseline failure. Tell the user now; do not let it be discovered at the gates and blamed on the new work.

## 4. Plan (top)

Spawn the architect with the user's request verbatim, constraints from the conversation, the context file path and the plan path `.orchestrator/plans/<slug>.md`. The plan follows `references/plan-format.md`: decisions, a risk level, the gates, and self-contained tasks, each with a role, a test mode and an acceptance check.

Show the user the task list (id, role, one line each), the risk level, the gates and any open questions, then ask for a go-ahead before building, unless they already said to proceed without asking. This is the cheapest place to catch a wrong direction.

## 5. Build

For each task, in dependency order:

- The brief holds only the plan path, the task id and "read the plan, do this task, run its acceptance check". Never paste the plan or code into a brief.
- **Tests first.** For a task marked `Tests: first`, the tester's task runs before the builder's, and the builder must make those tests pass without editing them. The tester never sees the implementation; the builder never rewrites the tests. If the builder reports a test is wrong, send that to the architect, not back to the builder.
- Tasks the plan marks as parallel and that touch different files go out in one message. Tasks on an external command that share a working tree run one at a time.
- Each agent ends with `STATUS: DONE | FAILED | BLOCKED`, the files changed and the check output. Trust a Claude subagent's report; do not re-read the diff. For a role on an external command, run the task's acceptance check yourself and treat a non-zero exit or failing check as `FAILED`.
- `FAILED` or `BLOCKED`: escalate one step, passing the previous report along. runner → builder → architect. Do not retry with the same role. A blocker that says the plan is wrong goes straight to the architect.
- Mark each finished task `done` in the plan file.

## 6. Gates

When all tasks are done, run:

```
python3 scripts/gate.py --plan .orchestrator/plans/<slug>.md
```

It runs every gate in order (lint, types, tests, build, smoke check, as the config or the plan's `## Gates` section lists them), stops at the first failure, and records the exact state of the code that passed. This is the only thing that counts as "the checks pass"; an agent saying so does not.

On a failure:

- If the cause is plain from the output and belongs to one task (a lint error, a missed import), send it to that task's role with the output.
- Otherwise spawn the debugger with the failing output and the plan path. It finds the root cause and applies the smallest fix.
- Run the gates again. After two failed rounds on the same gate, escalate to the architect; if that also fails, stop and bring the evidence to the user.

No one may make a gate pass by weakening it: no skipped or deleted tests, loosened assertions, lowered thresholds or silenced rules. A report that did so counts as `FAILED`.

## 7. Review

After the gates pass, spawn the reviewer with the plan path and the diff command (`git diff <base>...HEAD`, or `git diff HEAD` if nothing is committed yet). Use the top-tier model for the review when the plan says `Risk: high`.

- `APPROVE`: continue. Mention any `SHOULD` items in the final report; do not fix them unasked.
- `CHANGES_REQUIRED`: send the blockers to the builder (or the debugger if the cause is unclear), then run the gates again and have the reviewer check only the fix. Allow two review rounds, then bring what remains to the user.

## 8. Ship

Nothing leaves the machine until the gates have passed on exactly the code being pushed.

1. Commit the gated state. Any edit after the last gate run, including review fixes, needs a new gate run first.
2. Push or open a pull request only if the user asked for it. Never push to a production or default branch on your own initiative; prefer a feature branch and a pull request.
3. With the plugin installed, a hook blocks `git push` when the last gate run failed or `HEAD` differs from the code that passed. If it blocks you, run the gates; never clear the gate record or route around the hook. Only the user may decide to push without passing gates.
4. Deploy commands are not covered by the hook. Treat any deploy, release or publish step the same way: gates first, and only on the user's request.

## 9. Report

Finish with a short table: task, role and model that ran it, result, and any escalation. Then the gate results by name, the review verdict with any open `SHOULD` items, and what was and was not pushed.

## Rules that protect the savings

- Never delegate upward by default. Work reaches the top tier only through triage, high risk or escalation.
- Never have two roles do the same reading. The context file and the plan file are the only handoffs.
- Never let a subagent spawn further subagents.
- Scale the cycle to the task. A rename does not need a scout, a tester and a reviewer.
- The session you run in is billed too. If it is on a top-tier model and most work is delegated, mention once that `/model sonnet` for the session itself would save more.
