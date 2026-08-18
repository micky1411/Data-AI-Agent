BEGIN;

CREATE SCHEMA IF NOT EXISTS src AUTHORIZATION etl_rw;
CREATE SCHEMA IF NOT EXISTS stg AUTHORIZATION etl_rw;
CREATE SCHEMA IF NOT EXISTS mart AUTHORIZATION etl_rw;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION etl_rw;

CREATE TABLE IF NOT EXISTS src.customer_history (
    customer_id integer NOT NULL,
    customer_name text NOT NULL,
    email text NOT NULL,
    region text NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    current_flag boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS src.products (
    product_id integer NOT NULL,
    product_name text NOT NULL,
    category text NOT NULL,
    unit_price numeric(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS src.sales (
    sale_id text NOT NULL,
    customer_id integer NOT NULL,
    product_id integer NOT NULL,
    sale_timestamp timestamp NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(12, 2) NOT NULL,
    source_file text NOT NULL
);

CREATE TABLE IF NOT EXISTS stg.customer_history (
    customer_id integer NOT NULL,
    customer_name text NOT NULL,
    email text NOT NULL,
    region text NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    current_flag boolean NOT NULL,
    CONSTRAINT customer_dates_valid CHECK (
        effective_to IS NULL OR effective_to >= effective_from
    )
);

CREATE TABLE IF NOT EXISTS stg.products (
    product_id integer PRIMARY KEY,
    product_name text NOT NULL,
    category text NOT NULL,
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price > 0)
);

CREATE TABLE IF NOT EXISTS stg.sales (
    sale_id text PRIMARY KEY,
    customer_id integer NOT NULL,
    product_id integer NOT NULL,
    sale_timestamp timestamp NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price > 0),
    source_file text NOT NULL
);

CREATE TABLE IF NOT EXISTS mart.customer_dim (
    customer_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id integer NOT NULL,
    customer_name text NOT NULL,
    email text NOT NULL,
    region text NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    current_flag boolean NOT NULL,
    UNIQUE (customer_id, effective_from),
    CONSTRAINT customer_dim_dates_valid CHECK (
        effective_to IS NULL OR effective_to >= effective_from
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS one_current_customer_version
    ON mart.customer_dim (customer_id) WHERE current_flag;

CREATE TABLE IF NOT EXISTS mart.product_dim (
    product_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id integer NOT NULL UNIQUE,
    product_name text NOT NULL,
    category text NOT NULL,
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price > 0)
);

CREATE TABLE IF NOT EXISTS mart.sales_fact (
    sale_sk bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sale_id text NOT NULL UNIQUE,
    customer_sk bigint NOT NULL REFERENCES mart.customer_dim(customer_sk),
    product_sk bigint NOT NULL REFERENCES mart.product_dim(product_sk),
    sale_timestamp timestamp NOT NULL,
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price > 0),
    total_amount numeric(14, 2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    source_file text NOT NULL
);

CREATE TABLE IF NOT EXISTS audit.row_counts (
    recorded_at timestamp with time zone NOT NULL DEFAULT now(),
    layer text NOT NULL,
    table_name text NOT NULL,
    row_count bigint NOT NULL CHECK (row_count >= 0),
    PRIMARY KEY (recorded_at, layer, table_name)
);

GRANT USAGE ON SCHEMA src, stg, mart, audit TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA src, stg, mart, audit TO agent_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE etl_rw IN SCHEMA src, stg, mart, audit
    GRANT SELECT ON TABLES TO agent_ro;

COMMIT;
