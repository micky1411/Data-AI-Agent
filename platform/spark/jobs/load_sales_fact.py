"""Load one staged vendor file into the dimensional sales fact."""

from __future__ import annotations

from job_common import connect, process_date_argument, source_file


def main() -> None:
    file_name = source_file(process_date_argument())
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM mart.sales_fact WHERE source_file = %s", (file_name,))
            cursor.execute(
                """
                INSERT INTO mart.sales_fact (
                    sale_id, customer_sk, product_sk, sale_timestamp,
                    quantity, unit_price, source_file
                )
                SELECT
                    sales.sale_id, customer.customer_sk, product.product_sk,
                    sales.sale_timestamp, sales.quantity, sales.unit_price, sales.source_file
                FROM stg.sales AS sales
                JOIN mart.customer_dim AS customer
                  ON customer.customer_id = sales.customer_id
                 AND sales.sale_timestamp::date >= customer.effective_from
                 AND (
                    customer.effective_to IS NULL
                    OR sales.sale_timestamp::date <= customer.effective_to
                 )
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
            if loaded != staged:
                raise RuntimeError(f"fact load mismatch file={file_name} staged={staged} loaded={loaded}")
    print(f"Loaded {loaded} fact rows from {file_name}")


if __name__ == "__main__":
    main()
