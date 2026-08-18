"""Inject and reset deterministic failures in the local data platform."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = Path(__file__).resolve().parent / "state"
ACTIVE_FILE = STATE_DIR / "active_scenario"
MANIFEST_FILE = STATE_DIR / "manifest.json"
PROCESS_DATE = "2026-08-15"
SOURCE_FILE = "sales_20260815.csv"
SCENARIOS = (
    "missing_file",
    "corrupt_file",
    "db_transient_down",
    "schema_change",
    "scd2_join_bug",
    "duplicate_source_rows",
)


def run(command: list[str], *, capture: bool = False) -> str:
    print("+", " ".join(command))
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
        env=os.environ.copy(),
    )
    return result.stdout.strip() if capture else ""


def ensure_baseline_files() -> Path:
    run([sys.executable, "platform/seed/seed.py", "--generate-only"])
    return ROOT / "platform" / "seed" / "output" / "vendor-drop" / SOURCE_FILE


def minio(command: str) -> None:
    run([
        "docker", "compose", "run", "--rm", "--entrypoint", "/bin/sh",
        "seed-loader", "-c",
        "mc alias set local http://minio:9000 \"$MINIO_ROOT_USER\" "
        "\"$MINIO_ROOT_PASSWORD\" >/dev/null && " + command,
    ])


def upload(path: Path) -> None:
    relative = path.relative_to(ROOT / "platform" / "seed" / "output").as_posix()
    minio(f"mc cp /seed/{relative} local/vendor-drop/{SOURCE_FILE}")


def write_variant(kind: str, baseline: Path) -> Path:
    variant = baseline.parent / ".chaos_sales.csv"
    if kind == "corrupt_file":
        rows = list(csv.reader(baseline.open(encoding="utf-8")))
        with variant.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle, delimiter=";", lineterminator="\n").writerows(rows)
    else:
        with baseline.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        if kind == "schema_change":
            rows[0][rows[0].index("customer_id")] = "customer_number"
        elif kind == "duplicate_source_rows":
            duplicates = [row.copy() for row in rows[1:11]]
            for row in duplicates:
                row[0] += "-DUP"
            rows.extend(duplicates)
        with variant.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)
    return variant


def inject(scenario: str, transient_seconds: int) -> None:
    if ACTIVE_FILE.exists():
        raise RuntimeError(
            f"scenario {ACTIVE_FILE.read_text(encoding='utf-8').strip()} is active; run reset first"
        )
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    baseline = ensure_baseline_files()

    if scenario == "missing_file":
        minio(f"mc rm --force local/vendor-drop/{SOURCE_FILE}")
    elif scenario in {"corrupt_file", "schema_change", "duplicate_source_rows"}:
        upload(write_variant(scenario, baseline))
    elif scenario == "scd2_join_bug":
        ACTIVE_FILE.write_text(scenario + "\n", encoding="utf-8")
    elif scenario == "db_transient_down":
        run(["docker", "compose", "stop", "postgres"])
        spawn_delayed_restart(transient_seconds)

    if not ACTIVE_FILE.exists():
        ACTIVE_FILE.write_text(scenario + "\n", encoding="utf-8")
    manifest = {
        "scenario": scenario,
        "process_date": PROCESS_DATE,
        "source_file": SOURCE_FILE,
        "transient_seconds": transient_seconds if scenario == "db_transient_down" else None,
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Injected {scenario}. Trigger daily_sales_pipeline with process_date={PROCESS_DATE}.")


def spawn_delayed_restart(delay: int) -> None:
    command = [sys.executable, str(Path(__file__).resolve()), "_restart-postgres", "--delay", str(delay)]
    options: dict[str, object] = {"cwd": ROOT, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        options["start_new_session"] = True
    subprocess.Popen(command, **options)
    print(f"Postgres will restart automatically after {delay} seconds.")


def restart_postgres(delay: int) -> None:
    time.sleep(delay)
    run(["docker", "compose", "start", "postgres"])


def reset() -> None:
    run(["docker", "compose", "start", "postgres"])
    for path in (
        ACTIVE_FILE,
        MANIFEST_FILE,
        ROOT / "platform" / "seed" / "output" / "vendor-drop" / ".chaos_sales.csv",
    ):
        path.unlink(missing_ok=True)
    run([sys.executable, "platform/seed/seed.py"])
    print("Chaos state cleared; deterministic warehouse and MinIO baseline restored.")


def status() -> None:
    if not ACTIVE_FILE.exists():
        print("No active chaos scenario.")
        return
    print(MANIFEST_FILE.read_text(encoding="utf-8") if MANIFEST_FILE.exists() else ACTIVE_FILE.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inject_parser = subparsers.add_parser("inject", help="inject one fault into the baseline")
    inject_parser.add_argument("scenario", choices=SCENARIOS)
    inject_parser.add_argument("--transient-seconds", type=int, default=20)
    subparsers.add_parser("reset", help="restore deterministic Postgres and MinIO state")
    subparsers.add_parser("status", help="show the active scenario")
    restart_parser = subparsers.add_parser("_restart-postgres", help=argparse.SUPPRESS)
    restart_parser.add_argument("--delay", type=int, required=True)
    args = parser.parse_args()
    if args.command == "inject":
        inject(args.scenario, args.transient_seconds)
    elif args.command == "reset":
        reset()
    elif args.command == "status":
        status()
    else:
        restart_postgres(args.delay)


if __name__ == "__main__":
    main()
