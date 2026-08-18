#!/usr/bin/env bash
set -Eeuo pipefail

psql --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=etl_rw_password="$ETL_RW_PASSWORD" \
  --set=agent_ro_password="$AGENT_RO_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE etl_rw LOGIN PASSWORD %L', :'etl_rw_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'etl_rw') \gexec

SELECT format('CREATE ROLE agent_ro LOGIN PASSWORD %L', :'agent_ro_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_ro') \gexec

CREATE DATABASE dwh OWNER etl_rw;
REVOKE ALL ON DATABASE dwh FROM PUBLIC;
GRANT CONNECT ON DATABASE dwh TO agent_ro;
SQL

psql --set ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname dwh <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO agent_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE etl_rw
  GRANT SELECT ON TABLES TO agent_ro;
SQL
