"""Independent warehouse-wide quality gate."""

from __future__ import annotations

import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

from pipeline_common import report_failure


with DAG(
    dag_id="warehouse_quality_pipeline",
    description="Validate SCD2 integrity and source-to-fact reconciliation",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 15, tz="UTC"),
    catchup=False,
    default_args={
        "owner": "data-platform",
        "retries": 0,
        "on_failure_callback": report_failure,
    },
    tags=["dataops", "quality"],
) as dag:
    BashOperator(
        task_id="validate_warehouse",
        bash_command="python /opt/airflow/spark/jobs/audit_warehouse.py",
    )
