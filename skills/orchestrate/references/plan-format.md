# Plan file format

The plan is the only handoff between tiers. A builder or runner starts with no memory of the conversation, so every task must be executable from the file alone.

Path: `.orchestrator/plans/<short-slug>.md`

````markdown
# Plan: <feature name>

## Goal
Two or three sentences: what is being built and why. Include the user's constraints verbatim.

## Context
What an implementer must know and cannot guess: relevant modules and their paths, conventions to follow (naming, error handling, test style), existing helpers to reuse, things that must not change.

## Decisions
Each design choice that was made, with one line of reasoning. Implementers follow these and do not reopen them.

## Tasks

### T1: <imperative title>
- Tier: mid
- Depends on: none
- Parallel with: T2
- Files: `src/auth/session.ts` (edit), `src/auth/session.test.ts` (create)
- Steps:
  1. Concrete step naming the function, type or section to change.
  2. ...
- Acceptance: `npm test -- session` passes
- Status: todo

### T2: <imperative title>
- Tier: small
- Depends on: none
- Parallel with: T1
- Files: `src/utils/*.ts`
- Steps:
  1. Rename `getUsr` to `getUser` in every listed file and update imports.
- Acceptance: `grep -r "getUsr" src` returns nothing; `npm run typecheck` passes
- Status: todo

## Final check
`npm test && npm run build`
````

## Rules for the architect

- **Tag the cheapest tier that can do each task.**
  - `small`: no judgment needed. The steps fully determine the result: renames, moves, formatting, find and replace, boilerplate copied from a named example, config edits with given values.
  - `mid`: needs to write or change logic, but every decision is already made in the plan.
  - `top`: reserve for a task that needs judgment the plan cannot settle in advance, such as tuning an algorithm against results. This should be rare; prefer deciding it in the plan.
- **Split by tier.** If a task mixes logic with mechanical cleanup, make it two tasks so the cleanup runs on the small model.
- **Keep tasks small enough to verify.** One task, one acceptance check that a command can decide.
- **Name things exactly.** Paths, function names, signatures and expected values. An instruction like "update the relevant files" forces the implementer to redo your exploration.
- **Mark parallelism honestly.** Two tasks are parallel only if they touch different files and neither depends on the other.
- **Do not write the implementation.** Signatures, data shapes and short snippets that pin down a decision are fine; full code bodies waste top-tier tokens.
