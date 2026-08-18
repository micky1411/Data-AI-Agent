"""Download one vendor file, validate it with PySpark, and load src/stg."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

import boto3
from pyspark.sql import SparkSession, functions as F, types as T

from job_common import connect, process_date_argument, source_file


def main() -> None:
    process_date = process_date_argument()
    file_name = source_file(process_date)
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
    )
    schema = T.StructType([
        T.StructField("sale_id", T.StringType(), False),
        T.StructField("customer_id", T.IntegerType(), False),
        T.StructField("product_id", T.IntegerType(), False),
        T.StructField("sale_timestamp", T.TimestampType(), False),
        T.StructField("quantity", T.IntegerType(), False),
        T.StructField("unit_price", T.DecimalType(12, 2), False),
        T.StructField("source_file", T.StringType(), False),
    ])

    with tempfile.TemporaryDirectory(prefix="dataops-sales-") as temp_dir:
        local_file = Path(temp_dir) / file_name
        client.download_file("vendor-drop", file_name, str(local_file))
        with local_file.open(newline="", encoding="utf-8") as handle:
            actual_header = next(csv.reader(handle), [])
        expected_header = schema.fieldNames()
        if actual_header != expected_header:
            raise ValueError(
                f"vendor schema mismatch expected={expected_header} actual={actual_header}"
            )
        spark = (
            SparkSession.builder.master("local[2]")
            .appName(f"ingest-{file_name}")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )
        try:
            frame = (
                spark.read.option("header", True)
                .option("mode", "FAILFAST")
                .schema(schema)
                .csv(str(local_file))
            )
            required = schema.fieldNames()
            invalid = frame.filter(
                F.greatest(*[F.col(column).isNull().cast("int") for column in required]) > 0
            ).count()
            wrong_file = frame.filter(F.col("source_file") != file_name).count()
            rows = frame.orderBy("sale_id").collect()
            if not rows or invalid or wrong_file:
                raise ValueError(
                    f"invalid vendor file rows={len(rows)} null_rows={invalid} "
                    f"wrong_source_file_rows={wrong_file}"
                )
        finally:
            spark.stop()

    values = [tuple(row[column] for column in schema.fieldNames()) for row in rows]
    columns = ", ".join(schema.fieldNames())
    placeholders = ", ".join(["%s"] * len(schema.fieldNames()))
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM stg.sales WHERE source_file = %s", (file_name,))
            cursor.execute("DELETE FROM src.sales WHERE source_file = %s", (file_name,))
            cursor.executemany(
                f"INSERT INTO src.sales ({columns}) VALUES ({placeholders})", values
            )
            cursor.executemany(
                f"INSERT INTO stg.sales ({columns}) VALUES ({placeholders})", values
            )
    print(f"PySpark validated and loaded {len(values)} rows from {file_name}")


if __name__ == "__main__":
    main()
