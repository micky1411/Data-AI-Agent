# Agent Governance Rules — DataOps Agent Project

> This file governs every AI agent working in this repository.
> `CLAUDE.md` (read by Claude agents) and `AGENTS.md` (read by ChatGPT/Codex and other agents)
> MUST contain **identical rules**. See Rule 1.

## Rule 1 — Sync rule
`CLAUDE.md` and `AGENTS.md` must always contain identical rules. If you edit one, you MUST
apply the exact same edit to the other **in the same commit**. Before starting work, diff the
two files; if they have drifted, fixing the drift is your first action.

## Rule 2 — Project context rule
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) is the single source of truth for the project's
vision, short-term and long-term milestones, current status, and the task log.
- **Before starting any task**: read PROJECT_CONTEXT.md fully.
- **After finishing any task**: update it — mark the task's status, record what changed,
  record the verification evidence (exact commands run and their results), and note what
  comes next. This update is part of the task, not optional.

## Rule 3 — Real data rule
Reason only from real observed data. Run the code, query the database, read the actual logs,
inspect the actual files. Never state a conclusion you have not verified. If information is
missing or ambiguous, ask the user instead of assuming.

## Rule 4 — Ask freely
Ask the user as many clarifying questions as needed, before and during work. A wrong
assumption costs far more than a question.

## Rule 5 — Commit rule
Commit only when a task is (a) implemented, (b) **verified** — its acceptance criteria pass,
with the proof described in the commit message, and (c) **documented** — PROJECT_CONTEXT.md
updated. One task = one branch = one focused set of commits. Do not batch unrelated changes.
After every successful task commit, push the current task branch to GitHub and set its
upstream if needed. A task is not handed off for review until both the commit and push
succeed. If pushing is blocked by authentication, permissions, or connectivity, report the
exact error to the user and record the task as locally committed but not yet pushed.

## Rule 6 — Git workflow
- Never commit directly to `main` (the initial bootstrap commit is the only exception).
- Start every task from fresh `main`: `git checkout main && git pull`, then
  `git checkout -b task/<id>-<short-slug>` (e.g. `task/1.2-data-model`).
- Commit messages reference the task id from PROJECT_CONTEXT.md.
- Push task branches with `git push -u origin <branch>` after the first commit and
  `git push` after later commits.
- The **user** reviews and merges branches into `main`. Agents never merge to `main`.
- Parallel agent work is allowed only on explicitly disjoint directories.

## Rule 7 — Safety invariants (product code)
These are non-negotiable properties of the agent we are building:
- The LLM never holds raw credentials. All platform access goes through guarded adapters
  (`agent/adapters/`) that enforce read-only roles, row limits, statement timeouts, and
  schema allowlists.
- Every automated action must pass the policy engine and be recorded in the action ledger.
  Unknown situations always degrade to notify-only.
- Every root-cause claim in a report must cite concrete evidence (query + result, or log
  excerpt). A conclusion without evidence is a bug.
- No secrets in git. Use `.env` (gitignored) with a committed `.env.example`.

## Rule 8 — Verification rule
A task is not done until its acceptance criteria (defined in PROJECT_CONTEXT.md) pass and
the exact commands proving it are recorded in the task log. "It should work" is not done.

## Rule 9 — Scope rule
Do only the assigned task. If you discover a bug, gap, or good idea outside your task's
scope, add it as a new entry in PROJECT_CONTEXT.md ("Backlog / discovered items") instead of
expanding your current change.

## Rule 10 — Human authorship rule
All repository commits must be authored solely under the user's Git identity, with the
author name `micky1411`. AI agents must never identify themselves as repository contributors,
commit authors, or co-authors. Do not add AI names, bot identities, generated-by notices, or
`Co-Authored-By` trailers to commits, pull requests, source files, or documentation. Agent
identity may appear only in internal operational records such as the PROJECT_CONTEXT.md task
log, where it is needed for traceability; that record does not imply authorship or ownership.
Before committing, verify `git config user.name` is `micky1411`. Preserve the user's configured
email address unless the user explicitly provides a replacement.
