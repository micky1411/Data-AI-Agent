"""FastAPI entry point for Airflow failure events."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from agent.core.incidents import FailureEvent, IncidentState, InvalidTransition
from agent.core.store import IncidentStore


class AirflowFailurePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dag_id: str = Field(min_length=1, max_length=250)
    task_id: str = Field(min_length=1, max_length=250)
    run_id: str = Field(min_length=1, max_length=500)
    try_number: int = Field(ge=1)
    logical_date: str | None = None
    exception: str = Field(max_length=20_000)
    log_url: str = Field(min_length=1, max_length=4_000)


class TransitionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: IncidentState
    reason: str = Field(min_length=1, max_length=2_000)


def create_app(database_path: str | Path | None = None) -> FastAPI:
    store = IncidentStore(database_path or os.environ.get("INCIDENT_DB_PATH", "data/incidents.sqlite3"))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.initialize()
        yield

    app = FastAPI(title="DataOps Incident Listener", version="0.1.0", lifespan=lifespan)
    app.state.incident_store = store

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/events/airflow", status_code=status.HTTP_201_CREATED)
    def airflow_event(payload: AirflowFailurePayload, request: Request, response: Response) -> dict:
        incident, created = request.app.state.incident_store.record_failure(
            FailureEvent(**payload.model_dump())
        )
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return {"created": created, "incident": incident}

    @app.get("/incidents")
    def list_incidents(request: Request) -> list[dict]:
        return request.app.state.incident_store.list()

    @app.get("/incidents/{incident_id}")
    def get_incident(incident_id: str, request: Request) -> dict:
        try:
            return request.app.state.incident_store.get(incident_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="incident not found") from error

    @app.post("/incidents/{incident_id}/transitions")
    def transition_incident(
        incident_id: str, payload: TransitionPayload, request: Request
    ) -> dict:
        try:
            return request.app.state.incident_store.transition(
                incident_id, payload.state, payload.reason
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="incident not found") from error
        except InvalidTransition as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return app


app = create_app()
