"""Shared runtime helpers for local pipeline jobs."""

from __future__ import annotations

import argparse
import os
from datetime import date

import psycopg


def process_date_argument() -> date:
    parser = argparse.ArgumentParser()
    parser.add_argument("--process-date", required=True, type=date.fromisoformat)
    return parser.parse_args().process_date


def source_file(process_date: date) -> str:
    return f"sales_{process_date:%Y%m%d}.csv"


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DWH_DSN"])
