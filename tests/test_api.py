from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from crewai_contact_center import api


AUTH_HEADER = {"Authorization": "Bearer test-crewai-key"}
TENANT_HEADER = {"x-tenant-id": "tenant_id-value"}
AUTH_TENANT_HEADERS = AUTH_HEADER | TENANT_HEADER


@pytest.fixture(autouse=True)
def clear_kickoffs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREWAI_API_KEY", "test-crewai-key")
    with api._kickoffs_lock:
        api._kickoffs.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(api.app)


def valid_inputs() -> dict[str, object]:
    return {key: f"{key}-value" for key in api.REQUIRED_INPUTS}


def test_protected_endpoints_fail_closed_without_configured_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CREWAI_API_KEY", raising=False)

    response = client.get("/inputs")

    assert response.status_code == 503
    assert response.json()["detail"] == "CREWAI_API_KEY is required"


def test_protected_endpoints_require_bearer_token(client: TestClient) -> None:
    response = client.get("/inputs")

    assert response.status_code == 401
    assert response.json()["detail"] == "missing bearer token"


def test_protected_endpoints_reject_invalid_bearer_token(client: TestClient) -> None:
    response = client.get("/inputs", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid bearer token"


def test_auth_rejects_non_ascii_bearer_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        api._verify_auth("Bearer inválid")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid bearer token"


def test_inputs_endpoint_accepts_valid_bearer_token(client: TestClient) -> None:
    response = client.get("/inputs", headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json() == {"required_inputs": api.REQUIRED_INPUTS}


def test_kickoff_rejects_missing_required_inputs(client: TestClient) -> None:
    response = client.post(
        "/kickoff",
        headers=AUTH_HEADER,
        json={"inputs": {"call_id": "call-1", "tenant_id": "tenant-1"}},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "missing or blank required CrewAI inputs"
    assert "transcript" in detail["missing_inputs"]


def test_kickoff_rejects_blank_required_inputs(client: TestClient) -> None:
    inputs = valid_inputs()
    inputs["transcript"] = "   "

    response = client.post("/kickoff", headers=AUTH_TENANT_HEADERS, json={"inputs": inputs})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "missing or blank required CrewAI inputs"
    assert detail["blank_inputs"] == ["transcript"]


def test_kickoff_starts_with_valid_required_inputs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    submitted: dict[str, object] = {}

    class FakeExecutor:
        def submit(self, fn, *args):  # type: ignore[no-untyped-def]
            submitted["fn"] = fn
            submitted["args"] = args

    monkeypatch.setattr(api, "_executor", FakeExecutor())

    response = client.post(
        "/kickoff",
        headers=AUTH_TENANT_HEADERS,
        json={"inputs": valid_inputs()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "running"
    kickoff_id = body["kickoff_id"]
    assert submitted["args"][0] == kickoff_id
    assert submitted["args"][1] == valid_inputs()
    with api._kickoffs_lock:
        assert api._kickoffs[kickoff_id]["state"] == "running"
        assert api._kickoffs[kickoff_id]["tenant_id"] == "tenant_id-value"


def test_kickoff_requires_tenant_header(client: TestClient) -> None:
    response = client.post(
        "/kickoff",
        headers=AUTH_HEADER,
        json={"inputs": valid_inputs()},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "missing x-tenant-id"


def test_kickoff_rejects_tenant_header_mismatch(client: TestClient) -> None:
    response = client.post(
        "/kickoff",
        headers=AUTH_HEADER | {"x-tenant-id": "other-tenant"},
        json={"inputs": valid_inputs()},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "tenant mismatch"


def test_status_requires_matching_tenant_header(client: TestClient) -> None:
    with api._kickoffs_lock:
        api._kickoffs["kid-1"] = {
            "tenant_id": "tenant-1",
            "state": "completed",
            "started_at": 1.0,
            "finished_at": 2.0,
            "duration_seconds": 1.0,
            "result": {"ok": True},
            "error": None,
        }

    missing = client.get("/status/kid-1", headers=AUTH_HEADER)
    mismatch = client.get(
        "/status/kid-1",
        headers=AUTH_HEADER | {"x-tenant-id": "tenant-2"},
    )
    allowed = client.get(
        "/status/kid-1",
        headers=AUTH_HEADER | {"x-tenant-id": "tenant-1"},
    )

    assert missing.status_code == 403
    assert missing.json()["detail"] == "missing x-tenant-id"
    assert mismatch.status_code == 404
    assert mismatch.json()["detail"] == "unknown kickoff_id: kid-1"
    assert allowed.status_code == 200
    assert allowed.json()["kickoff_id"] == "kid-1"
    assert "tenant_id" not in allowed.json()
