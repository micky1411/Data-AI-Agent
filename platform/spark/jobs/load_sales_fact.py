"""Load one staged vendor file into the dimensional sales fact."""

from __future__ import annotations

from pathlib import Path

from job_common import connect, process_date_argument, source_file


CHAOS_SCENARIO = Path("/opt/airflow/chaos/active_scenario")


def main() -> None:
    file_name = source_file(process_date_argument())
    scenario = CHAOS_SCENARIO.read_text(encoding="utf-8").strip() if CHAOS_SCENARIO.exists() else ""
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM mart.sales_fact WHERE source_file = %s", (file_name,))
            faulty_join = scenario == "scd2_join_bug"
            customer_join = """
                  ON customer.customer_id = sales.customer_id
            """ if faulty_join else """
                  ON customer.customer_id = sales.customer_id
                 AND sales.sale_timestamp::date >= customer.effective_from
                 AND (
                    customer.effective_to IS NULL
                    OR sales.sale_timestamp::date <= customer.effective_to
                 )
            """
            cursor.execute(
                f"""
                INSERT INTO mart.sales_fact (
                    sale_id, customer_sk, product_sk, sale_timestamp,
                    quantity, unit_price, source_file
                )
                SELECT
                    {"sales.sale_id || '-dim-' || customer.customer_sk" if faulty_join else "sales.sale_id"},
                    customer.customer_sk, product.product_sk,
                    sales.sale_timestamp, sales.quantity, sales.unit_price, sales.source_file
                FROM stg.sales AS sales
                JOIN mart.customer_dim AS customer
                  {customer_join}
                JOIN mart.product_dim AS product
                  ON product.product_id = sales.product_id
                WHERE sales.source_file = %s
                ORDER BY sales.sale_id
                """,
                (file_name,),
            )
            loaded = cursor.rowcount
            cursor.execute(
                "SELECT count(*) FROM stg.sales WHERE source_file = %s", (file_name,)
            )
            staged = cursor.fetchone()[0]
            if loaded != staged and scenario != "scd2_join_bug":
                raise RuntimeError(f"fact load mismatch file={file_name} staged={staged} loaded={loaded}")
    print(f"Loaded {loaded} fact rows from {file_name} chaos_scenario={scenario or 'none'}")


if __name__ == "__main__":
    main()
