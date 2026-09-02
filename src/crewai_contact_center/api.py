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
import hmac
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import logfire
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

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


_json_formatter = JSONFormatter()
handler = logging.StreamHandler()
handler.setFormatter(_json_formatter)
logging.root.handlers = [handler]
logging.root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

for _uvi_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _uvi_logger = logging.getLogger(_uvi_name)
    _uvi_logger.handlers = [handler]
    _uvi_logger.propagate = False

logger = logging.getLogger("crewai_contact_center.api")

logfire.configure(
    token=os.getenv("LOGFIRE_TOKEN"),
    service_name="crewai-contact-center",
    send_to_logfire="if-token-present",
)

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
    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)


class KickoffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kickoff_id: str
    state: str


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kickoff_id: str
    state: str  # running | completed | error  (matches telephony-service connector contract)
    started_at: float
    finished_at: float | None = None
    duration_seconds: float | None = None
    result: Any | None = None
    error: str | None = None


def _verify_auth(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("CREWAI_API_KEY", "").strip()
    if not expected:
        logger.error("CREWAI_API_KEY is not configured; refusing protected request")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "CREWAI_API_KEY is required",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid bearer token")


def _check_api_key_configured() -> None:
    if not os.getenv("CREWAI_API_KEY"):
        raise RuntimeError(
            "CREWAI_API_KEY environment variable is required but not set. "
            "Refusing to start without authentication configured."
        )


_check_api_key_configured()


def _validate_tenant_scope(x_tenant_id: str | None, tenant_id: Any) -> str:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "tenant_id must be a non-empty string"},
        )
    expected = tenant_id.strip()
    actual = (x_tenant_id or "").strip()
    if not actual:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "missing x-tenant-id")
    if not hmac.compare_digest(actual.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tenant mismatch")
    return expected


def _run_crew(kickoff_id: str, inputs: dict[str, Any]) -> None:
    started = _kickoffs[kickoff_id]["started_at"]
    try:
        logger.info("kickoff %s starting (call_id=%s)", kickoff_id, inputs.get("call_id"))
        result = ContactCenterCrew().crew().kickoff(inputs=inputs)
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


def _validate_required_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in REQUIRED_INPUTS if key not in inputs]
    blank = [
        key
        for key in REQUIRED_INPUTS
        if key in inputs and _is_blank_required_value(inputs[key])
    ]
    if missing or blank:
        detail: dict[str, Any] = {
            "message": "missing or blank required CrewAI inputs",
            "required_inputs": REQUIRED_INPUTS,
        }
        if missing:
            detail["missing_inputs"] = missing
        if blank:
            detail["blank_inputs"] = blank
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)
    return dict(inputs)


def _is_blank_required_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


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
logfire.instrument_fastapi(app)


@app.get("/health")
def health() -> dict[str, Any]:
    with _kickoffs_lock:
        active = sum(1 for k in _kickoffs.values() if k["state"] == "running")
    return {"status": "ok", "active_kickoffs": active}


@app.get("/inputs")
def list_inputs(_: None = Depends(_verify_auth)) -> dict[str, list[str]]:
    return {"required_inputs": REQUIRED_INPUTS}


@app.post("/kickoff", response_model=KickoffResponse)
def kickoff(
    req: KickoffRequest,
    _: None = Depends(_verify_auth),
    x_tenant_id: str | None = Header(default=None, alias="x-tenant-id"),
) -> KickoffResponse:
    inputs = _validate_required_inputs(req.inputs)
    tenant_id = _validate_tenant_scope(x_tenant_id, inputs["tenant_id"])
    kickoff_id = str(uuid.uuid4())
    with _kickoffs_lock:
        _kickoffs[kickoff_id] = {
            "tenant_id": tenant_id,
            "state": "running",
            "started_at": time.time(),
            "finished_at": None,
            "duration_seconds": None,
            "result": None,
            "error": None,
        }
    _executor.submit(_run_crew, kickoff_id, inputs)
    return KickoffResponse(kickoff_id=kickoff_id, state="running")


@app.get("/status/{kickoff_id}", response_model=StatusResponse)
def get_status(
    kickoff_id: str,
    _: None = Depends(_verify_auth),
    x_tenant_id: str | None = Header(default=None, alias="x-tenant-id"),
) -> StatusResponse:
    tenant_id = (x_tenant_id or "").strip()
    if not tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "missing x-tenant-id")
    with _kickoffs_lock:
        record = _kickoffs.get(kickoff_id)
    record_tenant_id = record.get("tenant_id") if record else None
    if (
        not record
        or not isinstance(record_tenant_id, str)
        or not hmac.compare_digest(
            tenant_id.encode("utf-8"), record_tenant_id.encode("utf-8")
        )
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown kickoff_id: {kickoff_id}")
    response_record = {key: value for key, value in record.items() if key != "tenant_id"}
    return StatusResponse(kickoff_id=kickoff_id, **response_record)


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
