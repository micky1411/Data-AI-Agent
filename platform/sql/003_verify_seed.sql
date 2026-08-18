\set ON_ERROR_STOP on

DO $$
DECLARE
    customer_count integer;
    multi_version_count integer;
    current_version_errors integer;
    overlap_count integer;
    source_sales_count integer;
    fact_sales_count integer;
BEGIN
    SELECT count(DISTINCT customer_id),
           count(*) FILTER (WHERE version_count > 1)
    INTO customer_count, multi_version_count
    FROM (
        SELECT customer_id, count(*) AS version_count
        FROM mart.customer_dim
        GROUP BY customer_id
    ) AS versions;

    IF customer_count <> 100 THEN
        RAISE EXCEPTION 'expected 100 customers, found %', customer_count;
    END IF;
    IF multi_version_count < 20 THEN
        RAISE EXCEPTION 'expected at least 20%% multi-version customers, found % of %',
            multi_version_count, customer_count;
    END IF;

    SELECT count(*) INTO current_version_errors
    FROM (
        SELECT customer_id
        FROM mart.customer_dim
        GROUP BY customer_id
        HAVING count(*) FILTER (WHERE current_flag) <> 1
    ) AS invalid_current;
    IF current_version_errors <> 0 THEN
        RAISE EXCEPTION '% customers do not have exactly one current version',
            current_version_errors;
    END IF;

    SELECT count(*) INTO overlap_count
    FROM mart.customer_dim AS left_version
    JOIN mart.customer_dim AS right_version
      ON left_version.customer_id = right_version.customer_id
     AND left_version.customer_sk < right_version.customer_sk
     AND daterange(
            left_version.effective_from,
            coalesce(left_version.effective_to + 1, 'infinity'::date),
            '[)'
         ) && daterange(
            right_version.effective_from,
            coalesce(right_version.effective_to + 1, 'infinity'::date),
            '[)'
         );
    IF overlap_count <> 0 THEN
        RAISE EXCEPTION 'found % overlapping SCD2 version pairs', overlap_count;
    END IF;

    SELECT count(*) INTO source_sales_count FROM src.sales;
    SELECT count(*) INTO fact_sales_count FROM mart.sales_fact;
    IF source_sales_count <> 240 OR fact_sales_count <> source_sales_count THEN
        RAISE EXCEPTION 'sales mismatch: source=%, fact=%',
            source_sales_count, fact_sales_count;
    END IF;
END
$$;

SELECT
    (SELECT count(DISTINCT customer_id) FROM mart.customer_dim) AS customers,
    (SELECT count(*) FROM mart.customer_dim) AS customer_versions,
    (SELECT count(*) FROM (
        SELECT customer_id FROM mart.customer_dim
        GROUP BY customer_id HAVING count(*) > 1
    ) AS versioned) AS multi_version_customers,
    (SELECT count(*) FROM mart.product_dim) AS products,
    (SELECT count(*) FROM mart.sales_fact) AS sales,
    (SELECT sum(total_amount) FROM mart.sales_fact) AS total_sales;
