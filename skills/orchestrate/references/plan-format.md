# Plan file format

The plan is the handoff between roles. A tester, builder or runner starts with no memory of the conversation, so every task must be executable from the file alone.

Path: `.orchestrator/plans/<short-slug>.md`

````markdown
# Plan: <feature name>

## Goal
Two or three sentences: what is being built and why. Include the user's constraints verbatim.

## Risk
normal | high, with one line of reasoning.

## Context
Scout file: `.orchestrator/context/<slug>.md`
Anything beyond it that an implementer must know and cannot guess: things that must not change, helpers to reuse, conventions that matter for this change.

## Decisions
Each design choice that was made, with one line of reasoning. Implementers follow these and do not reopen them.

## Gates
- lint: `npm run lint`
- types: `npm run typecheck`
- test: `npm test`
- build: `npm run build`
- smoke: `node scripts/smoke.js`

## Tasks

### T1: Write tests for session expiry
- Role: tester
- Tests: n/a
- Depends on: none
- Parallel with: T3
- Files: `src/auth/session.test.ts` (create)
- Steps:
  1. Cover each acceptance criterion of T2, plus expiry exactly at the boundary and a malformed token.
- Acceptance: `npm test -- session` runs and the new tests fail because `isExpired` does not exist
- Status: todo

### T2: Implement session expiry
- Role: builder
- Tests: first
- Depends on: T1
- Parallel with: none
- Files: `src/auth/session.ts` (edit)
- Steps:
  1. Add `isExpired(session: Session, now: Date): boolean` ...
  2. ...
- Acceptance: `npm test -- session` passes
- Status: todo

### T3: Rename getUsr to getUser
- Role: runner
- Tests: none
- Depends on: none
- Parallel with: T1
- Files: `src/utils/*.ts`
- Steps:
  1. Rename `getUsr` to `getUser` in every listed file and update imports.
- Acceptance: `grep -r "getUsr" src` returns nothing; `npm run typecheck` passes
- Status: todo
````

## Rules for the architect

- **Give each task the cheapest role that can do it.**
  - `runner`: no judgment needed. The steps fully determine the result: renames, moves, formatting, find and replace, boilerplate copied from a named example, config edits with given values.
  - `builder`: logic must be written, but every decision is already made in the plan.
  - `tester`: writes the tests for a builder task from its acceptance criteria, before that task runs.
  - `architect`: reserve for a task that needs judgment the plan cannot settle in advance. This should be rare; prefer deciding it in the plan.
- **Choose a test mode for every task.**
  - `first`: a separate tester task comes before it. For new behaviour with clear inputs and outputs, for bug fixes, and for anything on a risky path. Independent tests check what was asked for, not what was built.
  - `with`: the builder writes tests alongside the code. For small or tightly coupled changes.
  - `none`: mechanical tasks that the gates already cover.
- **Write real gates.** Exact commands that exist in this project, fastest first. Include a smoke check that exercises the new behaviour for real whenever the project can be run: unit tests passing is not the same as the feature working. One gate per line, as `- name: \`command\``; the gate runner reads this section.
- **Set risk honestly.** `high` for authentication or authorization, payments, data migrations or deletion, concurrency, cryptography, or public interfaces others depend on. It buys a top-tier review.
- **Split by role.** If a task mixes logic with mechanical cleanup, make it two tasks so the cleanup runs on the small model.
- **Keep tasks small enough to verify.** One task, one acceptance check that a command can decide.
- **Name things exactly.** Paths, function names, signatures and expected values. "Update the relevant files" forces the implementer to redo your exploration.
- **Mark parallelism honestly.** Two tasks are parallel only if they touch different files and neither depends on the other.
- **Do not write the implementation.** Signatures, data shapes and short snippets that pin down a decision are fine; full code bodies waste top-tier tokens.
