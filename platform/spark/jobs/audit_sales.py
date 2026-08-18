"""Reconcile one source file across warehouse layers."""

from __future__ import annotations

from datetime import datetime, timezone

from job_common import connect, process_date_argument, source_file


def main() -> None:
    file_name = source_file(process_date_argument())
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
            if source_count == 0 or len({source_count, staged_count, fact_count}) != 1:
                raise RuntimeError(
                    f"count mismatch file={file_name} src={source_count} "
                    f"stg={staged_count} mart={fact_count}"
                )
            if staged_total != fact_total:
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
    print(f"Audit passed file={file_name} rows={fact_count} total={fact_total}")


if __name__ == "__main__":
    main()
