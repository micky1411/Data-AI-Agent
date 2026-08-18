# PROJECT_CONTEXT — DataOps Agent

> Living source of truth. Every agent reads this before starting a task and updates it after
> finishing one (Rule 2 in CLAUDE.md / AGENTS.md).

## Vision

An **AI Data Engineering Production Support Agent** — a product that watches data pipelines,
investigates every failure with cited evidence, auto-recovers known low-risk operational
failures under a strict policy engine, and investigates data-quality issues ("the job
succeeded but the numbers are wrong") the way a real data engineer would: reading the
SQL/PySpark code, inspecting tables, checking join cardinality and SCD2 logic, and proving
the root cause with queries. Complex fixes are prepared and tested in DEV and presented to a
human for approval — never applied to production autonomously. Long-term this is a startup
product; the simulated platform below is the first adapter target, not the product itself.

## Long-term roadmap

1. **v1 (current)** — Investigate + auto-recover against the simulated stack. See milestones.
2. **Incident memory** — knowledge base of past incidents; retrieval used as a hint, never a
   conclusion (anchoring risk).
3. **DEV code-fix agent** — agent branches the pipeline repo, writes a fix, tests it in DEV,
   opens a PR with evidence for human approval.
4. **Human-approved production changes** — approval workflow through existing CI/CD.
5. **Real-stack adapters** — Snowflake (trial), Databricks free edition, then customer stacks.
6. **OpenAI provider** — second implementation of the LLM provider abstraction.
7. **Productization** — packaging, multi-tenant, API-key based LLM access, pricing.

## V1 milestones

| ID | Milestone | Status |
|----|-----------|--------|
| M0 | Repo bootstrap & governance | ✅ Done |
| M1 | Simulated data platform (Airflow + Postgres + PySpark + MinIO, Docker Compose) | ⬜ Not started — **blocked on user installing Docker Desktop** |
| M2 | Incident core (listener, incident store, guarded adapters, context collector — no LLM) | ⬜ Not started |
| M3 | LLM investigator (provider abstraction, investigation loop, data-quality flagship) | ⬜ Not started |
| M4 | Policy engine + auto-recovery (YAML policies, allowlisted actions, action ledger) | ⬜ Not started |
| M5 | Streamlit dashboard (incidents, evidence chains, approve/reject, chaos panel) | ⬜ Not started |
| M6 | Evaluation harness + v1 hardening (scoreboard vs ground truth, demo script) | ⬜ Not started |

Full task breakdown with acceptance criteria: [docs/architecture.md](docs/architecture.md)
(§ Task packets). Tasks are sized for one agent session each.

## Task log

| Task | Agent | Branch | Status | Verification | Notes |
|------|-------|--------|--------|--------------|-------|
| T0.1 Bootstrap | Claude (Fable 5) | main (bootstrap exception, Rule 6) | ✅ Done | `git log` shows initial commit; `git diff --no-index CLAUDE.md AGENTS.md` is empty; skeleton dirs exist | Governance files, project context, README, architecture doc, directory skeleton |

## Next up

**T1.1 — Compose stack**: docker-compose with Airflow (LocalExecutor), Postgres (separate
`dwh` database + `agent_ro` read-only role), MinIO. Acceptance: `docker compose up` →
Airflow UI reachable, psql connects as both roles, MinIO console reachable.
**Prerequisite (user)**: install Docker Desktop (WSL2 backend). Not yet installed as of 2026-08-18.

## Open questions for the user

- Docker Desktop installed yet? (blocks M1)
- This repo lives inside OneDrive (`Desktop\Data-AI-Agent`). Docker bind-mounts + OneDrive
  sync can conflict and OneDrive can corrupt live Postgres data files. Recommendation when
  M1 starts: move the repo out of OneDrive (e.g. `C:\dev\Data-AI-Agent`) or exclude it from
  sync. Decision pending.

## Backlog / discovered items

- (empty — agents add out-of-scope discoveries here per Rule 9)

## Key project decisions (summary)

- **Purpose**: startup/product idea → adapter layer keeps the product stack-agnostic.
- **Sim stack**: Airflow ≈ Autosys, Postgres ≈ Snowflake, local PySpark ≈ EMR, MinIO ≈ S3/Blob.
- **LLM (dev)**: Claude Agent SDK via user's subscription, behind a provider abstraction;
  OpenAI + raw API keys later. Free/local only until shipping.
- **V1 scope**: investigate + auto-recover. No prod code changes by the agent in v1.
- **Eval-first**: every chaos scenario has documented ground truth
  ([docs/incidents-catalog.md](docs/incidents-catalog.md)); the eval runner scores the agent
  against it. V1 exit bar: ≥ 5 of 6 scenarios pass.
- **Coding workflow**: agents work mostly one at a time, branch-per-task, user merges.
