"""Warehouse-wide SCD2 and source-to-fact quality checks."""

from __future__ import annotations

from job_common import connect


def scalar(cursor, query: str):
    cursor.execute(query)
    return cursor.fetchone()[0]


def main() -> None:
    with connect() as connection:
        with connection.cursor() as cursor:
            current_errors = scalar(cursor, """
                SELECT count(*) FROM (
                    SELECT customer_id FROM mart.customer_dim
                    GROUP BY customer_id
                    HAVING count(*) FILTER (WHERE current_flag) <> 1
                ) invalid
            """)
            source_count = scalar(cursor, "SELECT count(*) FROM src.sales")
            fact_count = scalar(cursor, "SELECT count(*) FROM mart.sales_fact")
            source_total = scalar(cursor, "SELECT sum(quantity * unit_price) FROM src.sales")
            fact_total = scalar(cursor, "SELECT sum(total_amount) FROM mart.sales_fact")
            if current_errors or source_count != fact_count or source_total != fact_total:
                raise RuntimeError(
                    f"warehouse quality failed current_errors={current_errors} "
                    f"source_count={source_count} fact_count={fact_count} "
                    f"source_total={source_total} fact_total={fact_total}"
                )
    print(
        f"Warehouse quality passed rows={fact_count} total={fact_total} "
        f"current_version_errors={current_errors}"
    )


if __name__ == "__main__":
    main()
