"""Generate and load the deterministic local benchmark dataset."""

from __future__ import annotations

import argparse
import csv
import os
import random
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path


RANDOM_SEED = 20260818
CUSTOMER_COUNT = 100
HISTORICAL_CUSTOMER_COUNT = 30
PRODUCT_COUNT = 20
SALES_PER_DAY = 80
SALE_DATES = (date(2026, 8, 15), date(2026, 8, 16), date(2026, 8, 17))
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent / "output"
VENDOR_DROP = OUTPUT / "vendor-drop"


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category: str
    price: Decimal


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def generate() -> dict[str, int]:
    rng = random.Random(RANDOM_SEED)
    regions = ("Central", "East", "South", "West")
    categories = ("Books", "Electronics", "Home", "Office", "Outdoors")

    customer_rows: list[list[object]] = []
    for customer_id in range(1, CUSTOMER_COUNT + 1):
        region = regions[(customer_id - 1) % len(regions)]
        if customer_id <= HISTORICAL_CUSTOMER_COUNT:
            customer_rows.append([
                customer_id,
                f"Customer {customer_id:03d}",
                f"customer{customer_id:03d}@old.example.com",
                region,
                "2025-01-01",
                "2026-06-30",
                "false",
            ])
            region = regions[customer_id % len(regions)]
        customer_rows.append([
            customer_id,
            f"Customer {customer_id:03d}",
            f"customer{customer_id:03d}@example.com",
            region,
            "2026-07-01" if customer_id <= HISTORICAL_CUSTOMER_COUNT else "2025-01-01",
            "",
            "true",
        ])

    products = [
        Product(
            product_id=index,
            name=f"Product {index:02d}",
            category=categories[(index - 1) % len(categories)],
            price=Decimal("5.00") + Decimal(index * 275) / Decimal(100),
        )
        for index in range(1, PRODUCT_COUNT + 1)
    ]
    product_rows = [
        [product.product_id, product.name, product.category, f"{product.price:.2f}"]
        for product in products
    ]

    sale_header = [
        "sale_id", "customer_id", "product_id", "sale_timestamp",
        "quantity", "unit_price", "source_file",
    ]
    all_sales: list[list[object]] = []
    for sale_date in SALE_DATES:
        file_name = f"sales_{sale_date:%Y%m%d}.csv"
        daily_sales: list[list[object]] = []
        for sequence in range(1, SALES_PER_DAY + 1):
            product = rng.choice(products)
            moment = datetime.combine(sale_date, time(8)) + timedelta(
                seconds=rng.randrange(0, 12 * 60 * 60)
            )
            row = [
                f"S-{sale_date:%Y%m%d}-{sequence:04d}",
                rng.randint(1, CUSTOMER_COUNT),
                product.product_id,
                moment.isoformat(sep=" "),
                rng.randint(1, 5),
                f"{product.price:.2f}",
                file_name,
            ]
            daily_sales.append(row)
            all_sales.append(row)
        write_csv(VENDOR_DROP / file_name, sale_header, daily_sales)

    write_csv(
        OUTPUT / "customer_history.csv",
        [
            "customer_id", "customer_name", "email", "region",
            "effective_from", "effective_to", "current_flag",
        ],
        customer_rows,
    )
    write_csv(
        OUTPUT / "products.csv",
        ["product_id", "product_name", "category", "unit_price"],
        product_rows,
    )
    write_csv(OUTPUT / "sales.csv", sale_header, all_sales)
    return {
        "customers": CUSTOMER_COUNT,
        "customer_versions": len(customer_rows),
        "historical_customers": HISTORICAL_CUSTOMER_COUNT,
        "products": len(products),
        "sales": len(all_sales),
        "daily_files": len(SALE_DATES),
    }


def env_value(name: str) -> str:
    env_file = ROOT / ".env"
    if not env_file.exists():
        raise RuntimeError(".env is missing; copy .env.example to .env first")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            return value.strip()
    raise RuntimeError(f"{name} is missing from .env")


def run(command: list[str], *, stdin_path: Path | None = None) -> None:
    printable = " ".join(command)
    print(f"+ {printable}")
    stdin = stdin_path.open("r", encoding="utf-8") if stdin_path else None
    try:
        subprocess.run(command, cwd=ROOT, stdin=stdin, check=True, env=os.environ.copy())
    finally:
        if stdin:
            stdin.close()


def load() -> None:
    password = env_value("ETL_RW_PASSWORD")
    psql = [
        "docker", "compose", "exec", "-T", "-e", f"PGPASSWORD={password}",
        "postgres", "psql", "-h", "localhost", "-U", "etl_rw", "-d", "dwh",
        "-v", "ON_ERROR_STOP=1",
    ]
    run(psql, stdin_path=ROOT / "platform/sql/001_warehouse_schema.sql")
    run(psql, stdin_path=ROOT / "platform/sql/002_load_seed.sql")
    run(["docker", "compose", "run", "--rm", "seed-loader"])
    run(psql, stdin_path=ROOT / "platform/sql/003_verify_seed.sql")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate-only", action="store_true",
        help="write deterministic CSV fixtures without loading Postgres or MinIO",
    )
    args = parser.parse_args()
    counts = generate()
    print("Generated:", ", ".join(f"{key}={value}" for key, value in counts.items()))
    if not args.generate_only:
        load()
        print("Loaded Postgres and MinIO successfully.")


if __name__ == "__main__":
    main()
