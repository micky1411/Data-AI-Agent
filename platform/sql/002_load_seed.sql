\set ON_ERROR_STOP on

TRUNCATE TABLE
    audit.row_counts,
    mart.sales_fact,
    mart.product_dim,
    mart.customer_dim,
    stg.sales,
    stg.products,
    stg.customer_history,
    src.sales,
    src.products,
    src.customer_history
RESTART IDENTITY CASCADE;

\copy src.customer_history FROM '/seed/customer_history.csv' WITH (FORMAT csv, HEADER true)
\copy src.products FROM '/seed/products.csv' WITH (FORMAT csv, HEADER true)
\copy src.sales FROM '/seed/sales.csv' WITH (FORMAT csv, HEADER true)

INSERT INTO stg.customer_history
SELECT * FROM src.customer_history;

INSERT INTO stg.products
SELECT * FROM src.products;

INSERT INTO stg.sales
SELECT * FROM src.sales;

INSERT INTO mart.customer_dim (
    customer_id, customer_name, email, region,
    effective_from, effective_to, current_flag
)
SELECT
    customer_id, customer_name, email, region,
    effective_from, effective_to, current_flag
FROM stg.customer_history
ORDER BY customer_id, effective_from;

INSERT INTO mart.product_dim (product_id, product_name, category, unit_price)
SELECT product_id, product_name, category, unit_price
FROM stg.products
ORDER BY product_id;

INSERT INTO mart.sales_fact (
    sale_id, customer_sk, product_sk, sale_timestamp,
    quantity, unit_price, source_file
)
SELECT
    s.sale_id,
    c.customer_sk,
    p.product_sk,
    s.sale_timestamp,
    s.quantity,
    s.unit_price,
    s.source_file
FROM stg.sales AS s
JOIN mart.customer_dim AS c
  ON c.customer_id = s.customer_id
 AND s.sale_timestamp::date >= c.effective_from
 AND (c.effective_to IS NULL OR s.sale_timestamp::date <= c.effective_to)
JOIN mart.product_dim AS p
  ON p.product_id = s.product_id
ORDER BY s.sale_id;

INSERT INTO audit.row_counts (recorded_at, layer, table_name, row_count)
SELECT timestamp with time zone '2026-08-18 00:00:00+00', layer, table_name, row_count
FROM (
    SELECT 'src' AS layer, 'customer_history' AS table_name, count(*) AS row_count FROM src.customer_history
    UNION ALL SELECT 'src', 'products', count(*) FROM src.products
    UNION ALL SELECT 'src', 'sales', count(*) FROM src.sales
    UNION ALL SELECT 'mart', 'customer_dim', count(*) FROM mart.customer_dim
    UNION ALL SELECT 'mart', 'product_dim', count(*) FROM mart.product_dim
    UNION ALL SELECT 'mart', 'sales_fact', count(*) FROM mart.sales_fact
) AS counts;
