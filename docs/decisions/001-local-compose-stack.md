# ADR 001 — Local Docker Compose stack

## Status

Accepted for v1.

## Context

The product needs a free, reproducible platform that approximates the user's enterprise
experience without requiring Snowflake, IICS, Autosys, Azure, or AWS accounts. The repository
is currently inside a OneDrive-synchronized directory, where bind-mounted database files are
unsafe.

## Decision

Use Docker Compose with Airflow LocalExecutor, one PostgreSQL server containing separate
`airflow` and `dwh` databases, and MinIO. Use named Docker volumes for all mutable service
data. Bind-mount only source DAGs. Bind all host ports to `127.0.0.1`.

Airflow LocalExecutor is appropriate for this single-machine simulation and avoids the Redis
and worker containers required by CeleryExecutor. The product remains platform-independent
through adapters added in M2.

## Consequences

- The local stack is free, resettable, and reproducible.
- Docker needs at least 4 GB of memory.
- Local Compose is a development/evaluation environment, not a production deployment.
- Named volumes avoid OneDrive synchronizing live PostgreSQL and MinIO data.
- PySpark dependencies will require extending the Airflow image in T1.3.
