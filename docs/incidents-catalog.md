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

## Scenarios (to be implemented in T1.4)

| ID | Type | Summary |
|----|------|---------|
| `missing_file` | data | Expected vendor CSV never lands in MinIO; sensor times out. Correct action: no retries; pause downstream; notify. |
| `corrupt_file` | data | Vendor CSV malformed (bad delimiter/encoding); ingest job fails parsing. Notify with file evidence. |
| `db_transient_down` | infrastructure | Postgres briefly unreachable; job fails with connection error; DB healthy again by investigation time. Correct action: auto retry (L0/L1). |
| `schema_change` | code/data | A source column is renamed; transform fails referencing old name. Notify with column-diff evidence. |
| `scd2_join_bug` | code | Transform SQL variant drops `current_flag = 'Y'` from the customer_dim join; **pipeline succeeds** but mart totals inflate. Detected via audit anomaly or manual ask. Evidence: join cardinality + before/after counts + offending git commit. |
| `duplicate_source_rows` | data | Vendor file contains duplicated rows; totals inflate; audit row-count jumps. Evidence: duplicate keys in `src`. |
