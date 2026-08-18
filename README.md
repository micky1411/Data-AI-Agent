# DataOps Agent

An **AI Data Engineering Production Support Agent**: it watches data pipelines, investigates
every failure with cited evidence, auto-recovers known low-risk operational failures under a
strict policy engine, and investigates data-quality issues ("the job succeeded but the
numbers are wrong") the way a real data engineer would — reading the SQL/PySpark code,
checking join cardinality and SCD2 logic, and proving root cause with queries.

**Status**: early development. v1 targets a fully simulated, free, local data platform
(Airflow + Postgres + PySpark + MinIO via Docker Compose) with a fault-injection harness
that doubles as an evaluation benchmark.

## Repository map

| Path | What it is |
|------|-----------|
| [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) | Governance rules for AI coding agents (kept identical) |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Living source of truth: vision, milestones, task log |
| [docs/architecture.md](docs/architecture.md) | Architecture, component contracts, full task breakdown |
| [docs/incidents-catalog.md](docs/incidents-catalog.md) | Ground-truth answer key for injectable faults |
| `platform/` | The simulated data platform (Docker Compose, DAGs, Spark jobs, SQL, chaos CLI) |
| `agent/` | The product: listener, collectors, adapters, LLM investigator, policy, recovery |
| `dashboard/` | Streamlit incident dashboard |
| `evals/` | Scenario runner scoring the agent against ground truth |

## For AI agents working here

Read [CLAUDE.md](CLAUDE.md) (Claude) or [AGENTS.md](AGENTS.md) (others) first, then
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md). Work happens branch-per-task; the user merges.

## Quickstart

Not yet — arrives with Milestone 1 (`docker compose up` for the platform) and Milestone 6
(full demo walkthrough).
