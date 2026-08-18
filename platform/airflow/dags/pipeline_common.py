"""Shared failure reporting for simulated platform DAGs."""

from __future__ import annotations

import json
import logging
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


LOGGER = logging.getLogger(__name__)


def report_failure(context: dict) -> None:
    """Post a compact failure event; never hide the original task failure."""
    task_instance = context["task_instance"]
    payload = {
        "dag_id": task_instance.dag_id,
        "task_id": task_instance.task_id,
        "run_id": task_instance.run_id,
        "try_number": task_instance.try_number,
        "logical_date": str(context.get("logical_date")),
        "exception": str(context.get("exception")),
        "log_url": task_instance.log_url,
    }
    request = Request(
        os.environ["AGENT_WEBHOOK_URL"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=3) as response:
            LOGGER.info("Failure event delivered with HTTP %s", response.status)
    except (OSError, URLError) as error:
        LOGGER.warning("Failure webhook unavailable; event=%s error=%s", payload, error)
