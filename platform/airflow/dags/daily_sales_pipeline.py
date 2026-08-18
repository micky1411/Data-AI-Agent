"""Daily vendor sales ingestion and warehouse load."""

from __future__ import annotations

import os

import boto3
import pendulum
from airflow.sdk import DAG, PokeReturnValue, task
from airflow.providers.standard.operators.bash import BashOperator
from botocore.exceptions import ClientError

from pipeline_common import report_failure


DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 0,
    "on_failure_callback": report_failure,
}


with DAG(
    dag_id="daily_sales_pipeline",
    description="MinIO vendor file to PySpark ingest, Postgres mart load, and audit",
    schedule=None,
    start_date=pendulum.datetime(2026, 8, 15, tz="UTC"),
    catchup=False,
    default_args=DEFAULT_ARGS,
    params={"process_date": "2026-08-15"},
    tags=["dataops", "sales", "pyspark"],
) as dag:

    @task.sensor(poke_interval=5, timeout=60, mode="reschedule")
    def wait_for_vendor_file(process_date: str) -> PokeReturnValue:
        object_key = f"sales_{process_date.replace('-', '')}.csv"
        client = boto3.client(
            "s3",
            endpoint_url=os.environ["MINIO_ENDPOINT"],
            aws_access_key_id=os.environ["MINIO_ROOT_USER"],
            aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        )
        try:
            metadata = client.head_object(Bucket="vendor-drop", Key=object_key)
            return PokeReturnValue(
                is_done=True,
                xcom_value={"object_key": object_key, "size": metadata["ContentLength"]},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return PokeReturnValue(is_done=False)
            raise

    ingest = BashOperator(
        task_id="pyspark_ingest",
        bash_command=(
            "python /opt/airflow/spark/jobs/ingest_sales.py "
            "--process-date '{{ params.process_date }}'"
        ),
    )
    load = BashOperator(
        task_id="load_sales_fact",
        bash_command=(
            "python /opt/airflow/spark/jobs/load_sales_fact.py "
            "--process-date '{{ params.process_date }}'"
        ),
    )
    audit = BashOperator(
        task_id="audit_sales",
        bash_command=(
            "python /opt/airflow/spark/jobs/audit_sales.py "
            "--process-date '{{ params.process_date }}'"
        ),
    )

    wait_for_vendor_file("{{ params.process_date }}") >> ingest >> load >> audit
