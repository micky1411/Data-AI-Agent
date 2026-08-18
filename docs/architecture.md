# Architecture — DataOps Agent (v1)

## Overview

Two halves: a **simulated data platform** (what we monitor) and the **support agent**
(the product). The platform exists because we have no free access to enterprise stacks
(Autosys/IICS/Snowflake); it doubles as the **evaluation benchmark** — every injectable
fault has a documented ground-truth root cause, so investigation quality is measurable.

```
┌────────────────────── SIMULATED DATA PLATFORM (docker compose) ─────────────────────┐
│  MinIO (vendor file drops)  →  Airflow DAGs (PySpark + SQL jobs)  →  Postgres DWH   │
│  Dimensional model incl. SCD2 customer_dim; sales fact; staging → final tables      │
│  chaos/ fault-injection CLI: break things on demand — each fault has a documented   │
│  ground-truth cause in docs/incidents-catalog.md                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │ failure events (Airflow callbacks → webhook)
                                        ▼
┌──────────────────────────── SUPPORT AGENT (Python package) ─────────────────────────┐
│ event listener → incident store (SQLite) → context collector (deterministic)        │
│ → INVESTIGATOR (LLM via provider abstraction; Claude Agent SDK first)               │
│     tool access ONLY through guarded adapters                                       │
│ → POLICY ENGINE (declarative YAML; classifies L0–L3; gates every action)            │
│ → RECOVERY EXECUTOR (allowlisted actions; idempotent via action ledger)             │
│ → evidence-backed incident report (markdown + structured JSON)                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                     Streamlit dashboard: incidents, evidence, approve/reject
```

## Components and contracts

### Simulated platform (`platform/`)
- **docker-compose.yml** — Airflow (LocalExecutor), Postgres (two databases: `airflow`
  metadata + `dwh` warehouse; roles: `etl_rw`, `agent_ro`), MinIO. PySpark runs local-mode
  inside the Airflow worker container (keeps RAM modest on Windows/WSL2).
- **Data model** — `src` schema (raw landed data), `stg` schema (staging), `mart` schema
  (final). Tables: `sales` fact, SCD2 `customer_dim` (effective dates + `current_flag`),
  `product_dim`, audit/row-count tables.
- **DAGs** — 2–3 pipelines: file sensor on MinIO → PySpark ingest → SQL transforms →
  final load → audit step. Every DAG registers `on_failure_callback` posting to the agent's
  webhook.
- **chaos CLI** — `chaos inject <scenario>` / `chaos reset`. Scenarios and their ground
  truth live in [incidents-catalog.md](incidents-catalog.md).

### Support agent (`agent/`)
- **listener/** — FastAPI webhook receiver. Dedupe: one incident per (dag, run) failure.
- **core/** — incident model + SQLite store. State machine:
  `DETECTED → COLLECTING → INVESTIGATING → (AUTO_RECOVERING | AWAITING_APPROVAL | NOTIFY_ONLY) → VALIDATING → RESOLVED | ESCALATED`.
- **collectors/** — deterministic, LLM-free: task log tails (filtered), DAG structure,
  recent run history, related code files (via repo adapter), target-table stats. Output: a
  structured context bundle (JSON) small enough for an LLM context window.
- **adapters/** — the ONLY way any component (especially the LLM) touches the platform:
  - `airflow_adapter`: read DAG/task/run state and logs; write ops (`retry_task`,
    `clear_and_rerun`, `pause_dag`) are separately flagged and only callable by the
    recovery executor.
  - `warehouse_adapter`: connects as `agent_ro` only; enforces row LIMIT injection,
    statement timeout, schema allowlist; rejects DML/DDL.
  - `storage_adapter`: list/stat/head objects in MinIO. No writes.
  - `repo_adapter`: read files, `git log`/`git diff` over `platform/` code. No writes.
- **llm/** — provider abstraction: `complete(prompt, tools) -> ToolLoopResult`.
  Implementations: `claude_provider` (Claude Agent SDK, subscription auth), `mock_provider`
  (deterministic, for tests). Investigator imports the interface, never an SDK.
- **investigator/** — the LLM loop. Input: context bundle + tool access. Required output
  (structured): classification (`infrastructure | data | code`), root cause, **evidence list**
  (each item = the exact query/log inspected + the actual result), confidence, recommended
  action. Tool-call budget cap per investigation.
- **policy/** — YAML rules: (classification, confidence, matched scenario) → action tier:
  `auto_execute | propose_for_approval | notify_only`, mapped to L0–L3. Unknown → notify_only.
- **recovery/** — executes only allowlisted actions (`retry_task`, `clear_and_rerun`,
  `pause_downstream`, `notify`). Action ledger (SQLite) enforces idempotency (an action runs
  at most once per incident) and max-attempt caps (no retry storms).
- **reports/** — per-incident markdown report + JSON record: timeline, evidence chain,
  actions taken, outcome.

### Dashboard (`dashboard/`)
Streamlit: incident list (live), incident detail (timeline, evidence, context bundle),
approve/reject for `propose_for_approval` actions, chaos-injection panel for demos.

### Evals (`evals/`)
`evals run`: for each scenario — reset platform → inject fault → wait for agent → score:
correct classification? root cause matches ground truth? evidence present and real? correct
action taken (and nothing more)? Outputs a scoreboard. **V1 exit bar: ≥ 5/6 scenarios.**

## Safety invariants (see Rule 7)
1. LLM never holds raw credentials; adapters enforce read-only + guards.
2. Every action policy-gated + ledger-logged; unknown situations degrade to notify-only.
3. Every root-cause claim cites concrete evidence.

## Task packets

Statuses live in [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md). Each task ≈ one agent session.

### M0 — Bootstrap
- **T0.1** ✅ Governance files, project context, README, this doc, directory skeleton, initial commit.

### M1 — Simulated platform *(prereq: Docker Desktop installed)*
- **T1.1 Compose stack** — Airflow + Postgres (`dwh` DB, `etl_rw` + `agent_ro` roles) + MinIO.
  *Accept:* `docker compose up` → Airflow UI on localhost, `psql` connects as both roles
  (and `agent_ro` cannot INSERT), MinIO console reachable.
- **T1.2 Data model + seed** — DDL for `src`/`stg`/`mart`; seed generator producing realistic
  data incl. multi-version SCD2 customers; daily vendor CSV drops into MinIO.
  *Accept:* tables populated; ≥ 20% of customers have >1 dim version; files land in MinIO.
- **T1.3 Pipelines** — 2–3 DAGs: sensor → PySpark ingest → SQL transform → final load →
  audit step; failure callbacks wired (pointing at a stub URL until T2.1).
  *Accept:* happy-path end-to-end run succeeds; `mart` totals match a hand-computed check.
- **T1.4 Chaos CLI** — scenarios: `missing_file`, `corrupt_file`, `db_transient_down`,
  `schema_change` (renamed source column), `scd2_join_bug` (drops `current_flag` filter →
  silent inflated totals), `duplicate_source_rows`. Plus `chaos reset`.
  *Accept:* each scenario reliably produces its documented failure/corruption; reset
  restores green; ground truth documented in incidents-catalog.md.

### M2 — Incident core (no LLM)
- **T2.1 Listener + store** — webhook → incident record + state machine.
  *Accept:* injected failure → exactly one incident with correct metadata; duplicate
  callbacks don't create duplicate incidents.
- **T2.2 Guarded adapters** — all four adapters + unit-tested guards.
  *Accept:* tests prove unbounded SELECT gets LIMIT-injected, DML rejected, timeout
  enforced, non-allowlisted schema rejected, write ops unreachable from investigator API.
- **T2.3 Context collector** — deterministic bundle per incident.
  *Accept:* for every M1 scenario, the bundle demonstrably contains the smoking-gun
  evidence (assert in tests against fixture runs).

### M3 — LLM investigator
- **T3.1 Provider abstraction** — interface + Claude Agent SDK impl + mock.
  *Accept:* live round-trip works; `grep` shows zero SDK imports outside `agent/llm/`.
- **T3.2 Investigator loop** — tool-using investigation over the bundle; structured findings
  with mandatory evidence; tool budget cap.
  *Accept:* correctly diagnoses `missing_file` and `db_transient_down` with real evidence.
- **T3.3 Data-quality investigation (flagship)** — manual trigger ("why is total_sales
  high?") + audit-anomaly trigger; reads SQL via repo_adapter; proves join duplication via
  cardinality queries.
  *Accept:* on `scd2_join_bug`, identifies the missing `current_flag` filter, cites
  before/after row counts, and names the offending git commit; on `schema_change`,
  identifies the renamed column.

### M4 — Policy + recovery
- **T4.1 Policy engine** — YAML rules, L0–L3, deterministic.
  *Accept:* table-driven tests; unknown scenario → notify_only, always.
- **T4.2 Recovery executor + ledger** — allowlisted actions, idempotency, attempt caps.
  *Accept:* `db_transient_down` auto-recovers end-to-end unattended (fail → investigate →
  retry → validate → resolved); ledger blocks duplicate action in tests.
- **T4.3 Reports** — evidence-chain markdown + JSON per incident.
  *Accept:* human-readable reports generated for every scenario run.

### M5 — Dashboard
- **T5.1 Streamlit app** — incident list/detail, approve/reject, chaos panel.
  *Accept:* full demo driveable from the UI: inject → watch incident → read evidence →
  approve/reject.

### M6 — Evals + hardening
- **T6.1 Eval runner** — reset/inject/wait/score per scenario; scoreboard.
  *Accept:* ≥ 5/6 pass; scoreboard committed to `docs/`.
- **T6.2 Hardening + demo script** — fix failures; README walkthrough.
  *Accept:* a stranger reproduces the demo from README alone.

## Decision records
Significant decisions get an ADR in `docs/decisions/` (`NNN-title.md`: context, decision,
consequences). First ADRs to write during M1: stack choice, LocalExecutor vs Celery,
repo-out-of-OneDrive decision.
