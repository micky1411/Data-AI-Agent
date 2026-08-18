"""Concurrency-safe SQLite incident store."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.core.incidents import FailureEvent, IncidentState, require_transition


SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    dag_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    try_number INTEGER NOT NULL CHECK (try_number >= 1),
    logical_date TEXT,
    exception TEXT NOT NULL,
    log_url TEXT NOT NULL,
    state TEXT NOT NULL,
    event_count INTEGER NOT NULL DEFAULT 1 CHECK (event_count >= 1),
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (dag_id, run_id)
);
CREATE TABLE IF NOT EXISTS incident_transitions (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
    from_state TEXT,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incident_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
    task_id TEXT NOT NULL,
    try_number INTEGER NOT NULL,
    logical_date TEXT,
    exception TEXT NOT NULL,
    log_url TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS incident_transitions_incident
ON incident_transitions (incident_id, transition_id);
CREATE INDEX IF NOT EXISTS incident_events_incident
ON incident_events (incident_id, event_id);
"""


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentStore:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def initialize(self) -> None:
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)

    def record_failure(self, event: FailureEvent) -> tuple[dict, bool]:
        now = timestamp()
        incident_id = str(uuid.uuid4())
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT incident_id FROM incidents WHERE dag_id = ? AND run_id = ?",
                (event.dag_id, event.run_id),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE incidents
                    SET event_count = event_count + 1, last_seen_at = ?
                    WHERE incident_id = ?
                    """,
                    (now, existing["incident_id"]),
                )
                self._insert_event(connection, existing["incident_id"], event, now)
                connection.commit()
                return self.get(existing["incident_id"]), False

            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, dag_id, run_id, task_id, try_number, logical_date,
                    exception, log_url, state, created_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id, event.dag_id, event.run_id, event.task_id,
                    event.try_number, event.logical_date, event.exception,
                    event.log_url, IncidentState.DETECTED, now, now,
                ),
            )
            connection.execute(
                """
                INSERT INTO incident_transitions (
                    incident_id, from_state, to_state, reason, occurred_at
                ) VALUES (?, NULL, ?, 'failure event received', ?)
                """,
                (incident_id, IncidentState.DETECTED, now),
            )
            self._insert_event(connection, incident_id, event, now)
            connection.commit()
        return self.get(incident_id), True

    @staticmethod
    def _insert_event(
        connection: sqlite3.Connection, incident_id: str, event: FailureEvent, received_at: str
    ) -> None:
        connection.execute(
            """
            INSERT INTO incident_events (
                incident_id, task_id, try_number, logical_date, exception, log_url, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id, event.task_id, event.try_number, event.logical_date,
                event.exception, event.log_url, received_at,
            ),
        )

    def get(self, incident_id: str) -> dict:
        with self.connect() as connection:
            incident = connection.execute(
                "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
            if incident is None:
                raise KeyError(incident_id)
            transitions = connection.execute(
                """
                SELECT from_state, to_state, reason, occurred_at
                FROM incident_transitions WHERE incident_id = ? ORDER BY transition_id
                """,
                (incident_id,),
            ).fetchall()
            events = connection.execute(
                """
                SELECT task_id, try_number, logical_date, exception, log_url, received_at
                FROM incident_events WHERE incident_id = ? ORDER BY event_id
                """,
                (incident_id,),
            ).fetchall()
        result = dict(incident)
        result["transitions"] = [dict(row) for row in transitions]
        result["events"] = [dict(row) for row in events]
        return result

    def list(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM incidents ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def transition(self, incident_id: str, target: IncidentState, reason: str) -> dict:
        now = timestamp()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT state FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
            if row is None:
                raise KeyError(incident_id)
            current = IncidentState(row["state"])
            require_transition(current, target)
            connection.execute(
                "UPDATE incidents SET state = ? WHERE incident_id = ?",
                (target, incident_id),
            )
            connection.execute(
                """
                INSERT INTO incident_transitions (
                    incident_id, from_state, to_state, reason, occurred_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (incident_id, current, target, reason, now),
            )
            connection.commit()
        return self.get(incident_id)
