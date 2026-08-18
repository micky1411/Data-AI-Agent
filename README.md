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

Prerequisites: Docker Desktop with at least 4 GB of memory available to Docker.

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up --detach --build
docker compose ps
```

- Airflow UI: http://localhost:8080
- MinIO console: http://localhost:9001
- PostgreSQL: `localhost:5432` (`airflow` and `dwh` databases)

Credentials are the local-only values in `.env`. Change them freely; `.env` is ignored by
Git. Persistent service data uses named Docker volumes rather than OneDrive-backed bind
mounts. To stop the stack, run `docker compose down`. To deliberately delete all local
platform data and re-run database initialization, run `docker compose down --volumes`.
Airflow uses its development-only simple auth manager and grants admin access without login;
all published ports are restricted to the local machine. This configuration must never be
used as a production deployment.

### Load the deterministic benchmark data

With the stack running:

```powershell
python platform/seed/seed.py
```

This generates the same dataset on every run, loads the `src`, `stg`, `mart`, and `audit`
warehouse schemas, and uploads three daily sales files to MinIO's `vendor-drop` bucket.
The benchmark contains 100 customers; 30 have two SCD2 versions. Generated CSVs are local
runtime artifacts under `platform/seed/output/` and are intentionally ignored by Git. The
command fails if database counts, SCD2 invariants, fact/source parity, or the MinIO file count
do not match the benchmark contract.

### Run a pipeline

After building/restarting the Airflow image, open http://localhost:8080 and trigger
`daily_sales_pipeline` with `process_date` set to one of `2026-08-15`, `2026-08-16`, or
`2026-08-17`. Its tasks visibly separate file sensing, PySpark validation/ingestion,
dimensional fact loading, and reconciliation. `warehouse_quality_pipeline` independently
checks the complete warehouse. New DAGs are paused by default: switch each DAG on in the UI
before triggering it. A run triggered while paused remains queued until the DAG is switched on.

```powershell
docker compose build airflow-api-server
docker compose up --detach --force-recreate airflow-init airflow-api-server airflow-scheduler airflow-dag-processor
```
