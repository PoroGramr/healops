import os

os.environ["HEALOPS_API_TOKEN"] = "test-admin-secret"
os.environ["HEALOPS_WORKER_TOKEN"] = "test-worker-secret"
os.environ["HEALOPS_DB_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base, get_session
from app.main import app
from app.settings import settings


@pytest.fixture
def client():
    settings.healops_db_url = "sqlite://"
    settings.healops_api_token = "test-admin-secret"
    settings.healops_worker_token = "test-worker-secret"
    settings.healops_managed_containers = "healops-broken-app"
    settings.healops_auto_restart = False
    settings.healops_auto_approve_names = ""
    settings.healops_restart_limit = 2
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


ADMIN = {"Authorization": "Bearer test-admin-secret"}
WORKER = {"Authorization": "Bearer test-worker-secret"}


def observe(
    client, status="running", health="healthy", exit_code=0, name="healops-broken-app", logs=""
):
    return client.post(
        "/api/worker/observe",
        headers=WORKER,
        json={
            "id": "container-1",
            "name": name,
            "image": "demo:latest",
            "status": status,
            "health": health,
            "exit_code": exit_code,
            "logs": logs,
        },
    )


def test_auth_and_allowlist(client):
    assert client.get("/api/containers").status_code == 401
    assert client.get("/api/containers", headers=WORKER).status_code == 401
    assert client.post("/api/worker/claim", headers=ADMIN).status_code == 401
    assert observe(client, name="unregistered").status_code == 403
    assert client.get("/api/settings", headers=ADMIN).json()["auto_restart"] is False


def test_health_fault_and_dedup(client):
    assert observe(client).json()["created"] is False
    assert observe(client, health="unhealthy", logs="RuntimeError: demo").json()["created"] is True
    assert observe(client, health="unhealthy").json()["created"] is False
    incidents = client.get("/api/incidents", headers=ADMIN).json()
    assert len(incidents) == 1
    assert incidents[0]["diagnosis"]["provider"] == "rules"
    assert incidents[0]["plan"]["kind"] == "restart"
    assert client.get("/api/dashboard", headers=ADMIN).json()["open_incidents"] == 1
    assert observe(client, health="healthy").json()["created"] is False
    assert client.get("/api/incidents", headers=ADMIN).json()[0]["status"] == "resolved"


def test_exit_detection_and_approval_gate(client):
    assert observe(client, status="exited", exit_code=0).json()["created"] is False
    assert (
        observe(client, status="exited", exit_code=137, logs="Traceback Exception").json()[
            "created"
        ]
        is True
    )
    incident = client.get("/api/incidents", headers=ADMIN).json()[0]
    plan_id = incident["plan"]["id"]
    assert incident["exit_code"] == 137
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"] is None
    assert (
        client.post(f"/api/plans/{plan_id}/decision?approved=true", headers=WORKER).status_code
        == 401
    )
    assert (
        client.post(f"/api/plans/{plan_id}/decision?approved=true", headers=ADMIN).status_code
        == 200
    )
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"] is None
    settings.healops_auto_restart = True
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"]["kind"] == "restart"
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"] is None
    assert (
        client.post(
            f"/api/worker/plans/{plan_id}/result",
            headers=WORKER,
            json={"outcome": "success", "healthy": True, "detail": "stable"},
        ).json()["status"]
        == "resolved"
    )
    assert (
        client.post(
            f"/api/worker/plans/{plan_id}/result",
            headers=WORKER,
            json={"outcome": "success", "healthy": True},
        ).status_code
        == 409
    )


def test_failed_verification(client):
    observe(client, health="unhealthy")
    plan = client.get("/api/incidents", headers=ADMIN).json()[0]["plan"]
    client.post(f"/api/plans/{plan['id']}/decision?approved=true", headers=ADMIN)
    settings.healops_auto_restart = True
    client.post("/api/worker/claim", headers=WORKER)
    response = client.post(
        f"/api/worker/plans/{plan['id']}/result",
        headers=WORKER,
        json={"outcome": "success", "healthy": False, "detail": "bad health"},
    )
    assert response.json()["status"] == "failed"
    assert observe(client, health="unhealthy").json()["created"] is False
    assert len(client.get("/api/incidents", headers=ADMIN).json()) == 1
    observe(client, health="healthy")
    assert observe(client, health="unhealthy").json()["created"] is True


def test_recovered_before_approval_cancels_plan(client):
    observe(client, health="unhealthy")
    plan_id = client.get("/api/incidents", headers=ADMIN).json()[0]["plan"]["id"]
    client.post(f"/api/plans/{plan_id}/decision?approved=true", headers=ADMIN)
    observe(client, health="healthy")
    settings.healops_auto_restart = True
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"] is None
    assert client.get("/api/incidents", headers=ADMIN).json()[0]["plan"]["status"] == "cancelled"


def test_container_recreated_same_name(client):
    observe(client)
    response = client.post(
        "/api/worker/observe",
        headers=WORKER,
        json={
            "id": "new-id",
            "name": "healops-broken-app",
            "status": "running",
            "health": "healthy",
        },
    )
    assert response.status_code == 200
    assert len(client.get("/api/containers", headers=ADMIN).json()) == 1


def test_stale_worker_is_not_reported_healthy(client, monkeypatch):
    from app import main

    observe(client)
    monkeypatch.setattr(main, "stale", lambda _: True)
    summary = client.get("/api/dashboard", headers=ADMIN).json()
    assert summary["monitor_online"] is False
    assert summary["healthy"] == 0
    assert client.get("/api/containers", headers=ADMIN).json()[0]["status"] == "stale"


def test_auto_restart_requires_three_failures_and_exact_name(client):
    settings.healops_auto_restart = True
    settings.healops_auto_approve_names = "other-container"
    for _ in range(3):
        observe(client, health="unhealthy")
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"] is None
    settings.healops_auto_approve_names = "healops-broken-app"
    observe(client, health="unhealthy")
    incident = client.get("/api/incidents", headers=ADMIN).json()[0]
    assert incident["plan"]["status"] == "approved"
    assert "auto_approved" in [e["kind"] for e in incident["events"]]
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"]["kind"] == "restart"


def test_auto_restart_stops_at_hourly_circuit_limit(client):
    settings.healops_auto_restart = True
    settings.healops_auto_approve_names = "healops-broken-app"
    settings.healops_restart_limit = 1
    for _ in range(3):
        observe(client, health="unhealthy")
    first = client.get("/api/incidents", headers=ADMIN).json()[0]
    claimed = client.post("/api/worker/claim", headers=WORKER).json()["plan"]
    assert claimed["id"] == first["plan"]["id"]
    client.post(
        f"/api/worker/plans/{claimed['id']}/result",
        headers=WORKER,
        json={"outcome": "success", "healthy": True},
    )
    observe(client, health="healthy")
    for _ in range(3):
        observe(client, health="unhealthy")
    second = client.get("/api/incidents", headers=ADMIN).json()[0]
    assert second["status"] == "failed"
    assert second["plan"]["status"] == "blocked"
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"] is None


def test_stranded_execution_fails_closed_without_restarting(client):
    from datetime import timedelta
    from app.models import Incident, utcnow

    settings.healops_auto_restart = True
    settings.healops_auto_approve_names = "healops-broken-app"
    for _ in range(3):
        observe(client, health="unhealthy")
    plan = client.post("/api/worker/claim", headers=WORKER).json()["plan"]
    with next(app.dependency_overrides[get_session]()) as db:
        incident = db.get(Incident, 1)
        incident.updated_at = utcnow() - timedelta(minutes=3)
        db.commit()
    assert client.post("/api/worker/claim", headers=WORKER).json()["plan"] is None
    result = client.get("/api/incidents", headers=ADMIN).json()[0]
    assert result["status"] == "failed"
    assert result["plan"]["status"] == "failed"
    assert "execution_timeout" in [e["kind"] for e in result["events"]]
    assert (
        client.post(
            f"/api/worker/plans/{plan['id']}/result",
            headers=WORKER,
            json={"outcome": "success", "healthy": True},
        ).status_code
        == 409
    )
