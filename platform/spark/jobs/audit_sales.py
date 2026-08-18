"""Reconcile one source file across warehouse layers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from job_common import connect, process_date_argument, source_file


CHAOS_SCENARIO = Path("/opt/airflow/chaos/active_scenario")


def main() -> None:
    file_name = source_file(process_date_argument())
    scenario = CHAOS_SCENARIO.read_text(encoding="utf-8").strip() if CHAOS_SCENARIO.exists() else ""
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    (SELECT count(*) FROM src.sales WHERE source_file = %(file)s),
                    (SELECT count(*) FROM stg.sales WHERE source_file = %(file)s),
                    (SELECT count(*) FROM mart.sales_fact WHERE source_file = %(file)s),
                    (SELECT sum(quantity * unit_price) FROM stg.sales WHERE source_file = %(file)s),
                    (SELECT sum(total_amount) FROM mart.sales_fact WHERE source_file = %(file)s)
                """,
                {"file": file_name},
            )
            source_count, staged_count, fact_count, staged_total, fact_total = cursor.fetchone()
            mismatch = source_count == 0 or len({source_count, staged_count, fact_count}) != 1
            if mismatch and scenario != "scd2_join_bug":
                raise RuntimeError(
                    f"count mismatch file={file_name} src={source_count} "
                    f"stg={staged_count} mart={fact_count}"
                )
            if staged_total != fact_total and scenario != "scd2_join_bug":
                raise RuntimeError(
                    f"total mismatch file={file_name} stg={staged_total} mart={fact_total}"
                )
            recorded_at = datetime.now(timezone.utc)
            cursor.executemany(
                """
                INSERT INTO audit.row_counts (recorded_at, layer, table_name, row_count)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (recorded_at, "src", f"sales:{file_name}", source_count),
                    (recorded_at, "stg", f"sales:{file_name}", staged_count),
                    (recorded_at, "mart", f"sales_fact:{file_name}", fact_count),
                ],
            )
    if mismatch or staged_total != fact_total:
        print(
            f"Audit anomaly file={file_name} src={source_count} stg={staged_count} "
            f"mart={fact_count} stg_total={staged_total} mart_total={fact_total}"
        )
    else:
        print(f"Audit passed file={file_name} rows={fact_count} total={fact_total}")


if __name__ == "__main__":
    main()
