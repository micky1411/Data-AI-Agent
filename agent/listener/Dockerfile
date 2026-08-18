FROM python:3.14.0-slim-bookworm

WORKDIR /app
COPY pyproject.toml ./
COPY agent ./agent
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 agent && mkdir -p /data && chown agent:agent /data
USER agent

ENV INCIDENT_DB_PATH=/data/incidents.sqlite3
EXPOSE 8000
CMD ["uvicorn", "agent.listener.app:app", "--host", "0.0.0.0", "--port", "8000"]
