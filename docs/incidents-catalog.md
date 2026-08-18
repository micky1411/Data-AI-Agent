# Incidents Catalog — Ground Truth for Chaos Scenarios

> One entry per injectable fault. This is the answer key the eval runner scores against.
> Filled in during **T1.4** when each scenario is implemented. Do not let the investigator
> agent read this file at runtime — it would be cheating; the `repo_adapter` allowlist must
> exclude `docs/incidents-catalog.md`.

## Template

```
### <scenario_id>
- **Injection**: what `chaos inject <scenario_id>` actually does
- **Observable symptom**: what fails (or silently corrupts) and where
- **Ground-truth classification**: infrastructure | data | code
- **Ground-truth root cause**: precise statement
- **Smoking-gun evidence**: the specific log line / query result that proves it
- **Correct action**: what the agent should do (per policy tier)
- **Reset**: how `chaos reset` restores health
```

## Scenarios

| ID | Type | Summary |
|----|------|---------|
| `missing_file` | data | Expected vendor CSV never lands in MinIO; sensor times out. Correct action: no retries; pause downstream; notify. |
| `corrupt_file` | data | Vendor CSV malformed (bad delimiter/encoding); ingest job fails parsing. Notify with file evidence. |
| `db_transient_down` | infrastructure | Postgres briefly unreachable; job fails with connection error; DB healthy again by investigation time. Correct action: auto retry (L0/L1). |
| `schema_change` | code/data | A source column is renamed; transform fails referencing old name. Notify with column-diff evidence. |
| `scd2_join_bug` | code | Transform SQL variant drops `current_flag = 'Y'` from the customer_dim join; **pipeline succeeds** but mart totals inflate. Detected via audit anomaly or manual ask. Evidence: join cardinality + before/after counts + offending git commit. |
| `duplicate_source_rows` | data | Vendor file contains duplicated rows; totals inflate; audit row-count jumps. Evidence: duplicate keys in `src`. |

### missing_file
- **Injection**: removes `sales_20260815.csv` from MinIO.
- **Observable symptom**: `wait_for_vendor_file` times out after repeated 404 responses; downstream tasks are not run.
- **Ground-truth classification**: data.
- **Ground-truth root cause**: the expected vendor object did not arrive.
- **Smoking-gun evidence**: MinIO `HEAD vendor-drop/sales_20260815.csv` returns 404 while the DAG parameter resolves to that exact key.
- **Correct action**: pause downstream processing and notify the vendor/operator; do not retry a confirmed absent input indefinitely.
- **Reset**: regenerates and mirrors the canonical three vendor objects.

### corrupt_file
- **Injection**: replaces the comma-delimited object with a semicolon-delimited version.
- **Observable symptom**: the sensor succeeds, then `pyspark_ingest` fails before loading data.
- **Ground-truth classification**: data.
- **Ground-truth root cause**: the vendor supplied the wrong delimiter.
- **Smoking-gun evidence**: ingest logs show expected seven-column header versus one semicolon-containing header value; object bytes contain semicolons.
- **Correct action**: quarantine/notify with object metadata and header evidence; do not load it.
- **Reset**: replaces the object with the canonical comma-delimited file and reloads the warehouse.

### db_transient_down
- **Injection**: stops Postgres and launches a detached restart after 20 seconds (configurable).
- **Observable symptom**: work scheduled during the outage reports a connection failure; Postgres is healthy when investigated after the window.
- **Ground-truth classification**: infrastructure.
- **Ground-truth root cause**: temporary database unavailability, not bad input or transform code.
- **Smoking-gun evidence**: connection-refused/closed logs at failure time plus a later successful `pg_isready` health check.
- **Correct action**: bounded automatic retry after confirming health (L0/L1).
- **Reset**: starts Postgres immediately and reloads/verifies the deterministic baseline.

### schema_change
- **Injection**: renames CSV header `customer_id` to `customer_number` without changing the pipeline contract.
- **Observable symptom**: the sensor succeeds and `pyspark_ingest` rejects the header.
- **Ground-truth classification**: code/data.
- **Ground-truth root cause**: the upstream schema changed incompatibly.
- **Smoking-gun evidence**: ingest log reports `expected=[..., customer_id, ...]` and `actual=[..., customer_number, ...]`.
- **Correct action**: notify and propose a reviewed contract/code update; never silently map by position.
- **Reset**: restores the canonical header and reloads the warehouse.

### scd2_join_bug
- **Injection**: activates the committed faulty transform variant that joins customer history only by business key, omitting the temporal SCD2 predicate.
- **Observable symptom**: the daily DAG succeeds but emits an audit anomaly and produces more fact rows and sales value than staging.
- **Ground-truth classification**: code.
- **Ground-truth root cause**: sales for customers with two dimension versions join twice.
- **Smoking-gun evidence**: join cardinality grouped by `sale_id` is greater than one; the code path lacks effective-date predicates; staging/fact counts and totals diverge.
- **Correct action**: notify/propose a code fix restoring the temporal predicate, test in DEV, and require human approval.
- **Reset**: disables the faulty variant and reloads canonical facts.

### duplicate_source_rows
- **Injection**: appends ten copies of business transactions with distinct transport IDs ending `-DUP`.
- **Observable symptom**: the daily pipeline loads 90 rows instead of the canonical 80; the warehouse audit rejects the 250-row/inflated-total warehouse.
- **Ground-truth classification**: data.
- **Ground-truth root cause**: duplicate business events arrived in the vendor file despite distinct row identifiers.
- **Smoking-gun evidence**: grouping source rows by customer, product, timestamp, quantity, and unit price (excluding `sale_id`) returns ten duplicate pairs; IDs identify the copied rows.
- **Correct action**: quarantine/notify and obtain a corrected file; do not guess which event is authoritative.
- **Reset**: restores the canonical 80-row file and reloads/verifies the 240-row warehouse.
