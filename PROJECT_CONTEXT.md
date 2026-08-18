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
| M1 | Simulated data platform (Airflow + Postgres + PySpark + MinIO, Docker Compose) | ✅ Done |
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
| T0.2 Push workflow | Codex | `task/0.2-push-workflow` | ✅ Done | `Get-FileHash` reports governance files identical; `git diff --check` passes; `git push -u origin main` and `git push -u origin task/0.2-push-workflow` succeed | Require every agent to push each successfully completed task commit to GitHub; Git Credential Manager authentication configured and both branches published |
| T1.1 Compose stack | Codex | `task/1.1-compose-stack` | ✅ Done | `docker compose config --quiet` passes; `docker compose ps --all` reports Postgres, MinIO, Airflow API server, scheduler, and DAG processor healthy; Airflow UI/health and MinIO console return HTTP 200; Airflow reports `LocalExecutor`; `etl_rw` and `agent_ro` connect to `dwh`; `agent_ro` INSERT fails with `permission denied`; MinIO init creates `vendor-drop` | Pinned local stack, named volumes, loopback-only ports, DWH roles, supported Airflow 3 simple auth, README quickstart, ADR 001 |
| T1.2 Data model + seed | Codex | `task/1.2-data-model-seed` | ✅ Done | `python platform/seed/seed.py` succeeds repeatedly and its embedded checks report 100 customers, 130 customer versions, 30 multi-version customers, 20 products, 240 source/fact sales, total 23370.50, no SCD2 overlaps, exactly one current version per customer, and 3 MinIO vendor files; generation hashes are identical across runs; `docker compose config --quiet`, `python -m py_compile`, and `git diff --check` pass | Added `src`/`stg`/`mart`/`audit` DDL, deterministic CSV generator, idempotent load, SCD2 and fact model, MinIO seed loader, executable benchmark verification |
| T1.3 Pipelines | Codex | `task/1.3-pipelines` | ✅ Done | Clean custom-image build from official Airflow succeeds with Java 17, PySpark 4.2, and compatible S3/Postgres clients; Airflow discovers 2 DAGs with zero import errors; end-to-end `daily_sales_pipeline` reports all 4 tasks successful and reconstructs 80 removed rows totaling 7339.25, matching an independent CSV calculation; `warehouse_quality_pipeline` succeeds over 240 rows totaling 23370.50; Python compile, Compose validation, and `git diff --check` pass | Added shared Airflow JWT/API signing config, custom runtime image, MinIO sensor, PySpark ingest, idempotent dimensional load, per-file audit, warehouse quality DAG, and failure callback to the future listener URL |
| T1.4 Chaos CLI | Codex | `task/1.4-chaos-cli` | ✅ Done | Live injections proved: missing object returns MinIO 404; corrupt delimiter and renamed header fail ingest with distinct actual/expected header evidence; transient Postgres stops and auto-recovers healthy; duplicates load 90 daily/250 warehouse rows and warehouse audit fails at 24230.75; faulty SCD2 join turns 80 staged into 104 fact rows and 7339.25 into 9756.50 while the daily audit records an anomaly; reset then passes ingest/load/daily audit and warehouse audit at 240 rows/23370.50; all services healthy; compile, Compose validation, and `git diff --check` pass | Added six mutually exclusive deterministic injections, delayed DB recovery, canonical reset/status, runtime-only scenario state, strict CSV contract validation, benchmark-aware warehouse audit, full ground-truth catalog, and README usage |

## Next up

**T2.1 — Listener + store**: receive Airflow failure callbacks, persist incidents with the
defined state machine, and deduplicate repeated callbacks for the same DAG run.

## Open questions for the user

- (none)

## Backlog / discovered items

- Governance commits T0.3/T0.4 (`f811822`, `93ad7f2`) exist on
  `origin/task/0.2-push-workflow` but were made after PR #1 was merged and are therefore not
  in `main`. Merge or cherry-pick them separately so the human-authorship rule is present on
  the default branch. T1.1 still used the required `micky1411 <vibhavkatta123@gmail.com>`
  local Git identity.

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
- **Local persistence**: mutable PostgreSQL, MinIO, and Airflow log data use Docker named
  volumes, so live service data is not synchronized through OneDrive.
