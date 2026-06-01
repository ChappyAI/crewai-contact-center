"""FastAPI wrapper exposing the CrewAI contact center crew as an HTTP service.

API mirrors CrewAI Enterprise so it is drop-in compatible with consumers that
were originally built against the managed product:

    GET  /inputs              -> list required input keys
    POST /kickoff             -> start a crew run, returns kickoff_id
    GET  /status/{kickoff_id} -> poll run status + final result
    GET  /health              -> liveness probe for Fly.io
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from dotenv import load_dotenv

load_dotenv()

from crewai_contact_center.crew import ContactCenterCrew


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "service": "crewai-contact-center",
            "message": record.getMessage(),
            "module": record.module,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

logger = logging.getLogger("crewai_contact_center.api")

REQUIRED_INPUTS: list[str] = [
    "call_id",
    "tenant_id",
    "transcript",
    "duration_seconds",
    "sentiment",
    "agent_notes",
    "disposition",
    "agent_id",
    "caller_number",
    "caller_history",
    "available_agents",
    "queue_depths",
    "sla_metrics",
    "campaign_id",
    "analysis_period",
    "contact_rate",
    "answer_rate",
    "conversion_rate",
    "abandon_rate",
    "avg_handle_time",
    "list_remaining",
    "transcript_chunk",
    "previous_sentiment",
    "elapsed_seconds",
]

MAX_WORKERS = int(os.getenv("CREW_MAX_WORKERS", "4"))
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="crew")
_kickoffs: dict[str, dict[str, Any]] = {}
_kickoffs_lock = threading.Lock()


class KickoffRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class KickoffResponse(BaseModel):
    kickoff_id: str
    state: str


class StatusResponse(BaseModel):
    kickoff_id: str
    state: str  # running | completed | error  (matches telephony-service connector contract)
    started_at: float
    finished_at: float | None = None
    duration_seconds: float | None = None
    result: Any | None = None
    error: str | None = None


def _verify_auth(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("CREWAI_API_KEY")
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service not configured: CREWAI_API_KEY not set")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid bearer token")


def _check_api_key_configured() -> None:
    """Validate CREWAI_API_KEY is set at import time / startup."""
    if not os.getenv("CREWAI_API_KEY"):
        raise RuntimeError(
            "CREWAI_API_KEY environment variable is required but not set. "
            "Refusing to start without authentication configured."
        )


_check_api_key_configured()


def _run_crew(kickoff_id: str, inputs: dict[str, Any]) -> None:
    started = _kickoffs[kickoff_id]["started_at"]
    try:
        merged = _merge_with_defaults(inputs)
        logger.info("kickoff %s starting (call_id=%s)", kickoff_id, merged.get("call_id"))
        result = ContactCenterCrew().crew().kickoff(inputs=merged)
        with _kickoffs_lock:
            _kickoffs[kickoff_id].update(
                state="completed",
                finished_at=time.time(),
                duration_seconds=time.time() - started,
                result=_serialize_result(result),
            )
        logger.info("kickoff %s completed in %.1fs", kickoff_id, time.time() - started)
    except Exception as exc:
        logger.exception("kickoff %s failed", kickoff_id)
        with _kickoffs_lock:
            _kickoffs[kickoff_id].update(
                state="error",
                finished_at=time.time(),
                duration_seconds=time.time() - started,
                error=f"{type(exc).__name__}: {exc}",
            )


def _merge_with_defaults(inputs: dict[str, Any]) -> dict[str, Any]:
    """Fill missing required keys with empty strings so YAML templating never KeyErrors.

    Crew tasks template via {var} substitution; a missing key crashes the run.
    """
    return {key: inputs.get(key, "") for key in REQUIRED_INPUTS} | inputs


def _serialize_result(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "raw"):
        return {"raw": str(result.raw), "tasks_output": getattr(result, "tasks_output", None)}
    return str(result)


app = FastAPI(
    title="Contact Center Crew API",
    description="Self-hosted CrewAI runtime mirroring CrewAI Enterprise endpoints.",
    version="0.2.0",
)


@app.get("/health")
def health() -> dict[str, Any]:
    with _kickoffs_lock:
        active = sum(1 for k in _kickoffs.values() if k["state"] == "running")
    return {"status": "ok", "active_kickoffs": active}


@app.get("/inputs")
def list_inputs(_: None = Depends(_verify_auth)) -> dict[str, list[str]]:
    return {"required_inputs": REQUIRED_INPUTS}


@app.post("/kickoff", response_model=KickoffResponse)
def kickoff(req: KickoffRequest, _: None = Depends(_verify_auth)) -> KickoffResponse:
    kickoff_id = str(uuid.uuid4())
    with _kickoffs_lock:
        _kickoffs[kickoff_id] = {
            "state": "running",
            "started_at": time.time(),
            "finished_at": None,
            "duration_seconds": None,
            "result": None,
            "error": None,
        }
    _executor.submit(_run_crew, kickoff_id, req.inputs)
    return KickoffResponse(kickoff_id=kickoff_id, state="running")


@app.get("/status/{kickoff_id}", response_model=StatusResponse)
def get_status(kickoff_id: str, _: None = Depends(_verify_auth)) -> StatusResponse:
    with _kickoffs_lock:
        record = _kickoffs.get(kickoff_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown kickoff_id: {kickoff_id}")
    return StatusResponse(kickoff_id=kickoff_id, **record)


def serve() -> None:
    """Entry point for `crewai_contact_center_api` script (uvicorn server)."""
    import uvicorn

    uvicorn.run(
        "crewai_contact_center.api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    serve()
