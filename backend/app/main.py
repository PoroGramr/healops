import hmac
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import (
    Approval,
    Container,
    Diagnosis,
    Incident,
    IncidentEvent,
    IncidentStatus,
    RemediationExecution,
    RemediationPlan,
    VerificationResult,
    utcnow,
)
from app.settings import settings

OPEN = {
    s.value for s in IncidentStatus if s not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)
}


def require(token: str, expected: str) -> None:
    if not expected or not hmac.compare_digest(token, f"Bearer {expected}"):
        raise HTTPException(401, "Invalid credentials")


def admin(authorization: str = Header(default="")):
    require(authorization, settings.healops_api_token)


def worker(authorization: str = Header(default="")):
    require(authorization, settings.healops_worker_token)


class Observation(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    image: str = Field(default="", max_length=512)
    status: str = Field(max_length=32)
    health: str = Field(default="none", max_length=32)
    exit_code: int | None = None
    logs: str = Field(default="", max_length=8192)


class Result(BaseModel):
    outcome: str
    healthy: bool
    detail: str = Field(default="", max_length=2048)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.healops_api_token or not settings.healops_worker_token:
        raise RuntimeError("Set distinct HEALOPS_API_TOKEN and HEALOPS_WORKER_TOKEN")
    if settings.healops_api_token == settings.healops_worker_token:
        raise RuntimeError("Admin and worker credentials must differ")
    yield


app = FastAPI(title="HealOps API", lifespan=lifespan)


def event(db: Session, incident: Incident, kind: str, detail: str = ""):
    db.add(IncidentEvent(incident_id=incident.id, kind=kind, detail=detail))


def stale(container: Container) -> bool:
    # SQLite returns naive UTC timestamps; normalize both sides before comparing.
    return utcnow().replace(tzinfo=None) - container.last_seen.replace(tzinfo=None) > timedelta(
        seconds=20
    )


def maybe_auto_approve(db: Session, incident: Incident, container: Container):
    if (
        not settings.healops_auto_restart
        or container.name not in settings.auto_approve_names
        or container.failure_streak < 3
        or incident.status != "proposed"
    ):
        return
    plan = db.scalar(select(RemediationPlan).where(RemediationPlan.incident_id == incident.id))
    if plan is None or plan.kind != "restart" or plan.status != "proposed":
        return
    recent = db.scalar(
        select(func.count())
        .select_from(RemediationExecution)
        .join(RemediationPlan, RemediationExecution.plan_id == RemediationPlan.id)
        .join(Incident, RemediationPlan.incident_id == Incident.id)
        .where(
            Incident.container_name == container.name,
            RemediationExecution.created_at >= utcnow() - timedelta(hours=1),
        )
    )
    if recent >= settings.healops_restart_limit:
        incident.status = "failed"
        plan.status = "blocked"
        event(db, incident, "circuit_open", "Hourly restart limit reached")
        return
    plan.status = "approved"
    incident.status = "awaiting_approval"
    db.flush()
    db.add(Approval(plan_id=plan.id, approved=True, actor="policy"))
    event(db, incident, "auto_approved", "Registered-container restart after 3 failures")


def serialize_incident(db: Session, incident: Incident):
    diagnosis = db.scalar(
        select(Diagnosis).where(Diagnosis.incident_id == incident.id).order_by(Diagnosis.id.desc())
    )
    plan = db.scalar(
        select(RemediationPlan)
        .where(RemediationPlan.incident_id == incident.id)
        .order_by(RemediationPlan.id.desc())
    )
    events = db.scalars(
        select(IncidentEvent)
        .where(IncidentEvent.incident_id == incident.id)
        .order_by(IncidentEvent.id)
    ).all()
    return {
        "id": incident.id,
        "container_id": incident.container_id,
        "container_name": incident.container_name,
        "image": incident.image,
        "exit_code": incident.exit_code,
        "status": incident.status,
        "logs": incident.logs,
        "created_at": incident.created_at,
        "diagnosis": {
            "cause": diagnosis.cause,
            "evidence": diagnosis.evidence,
            "confidence": diagnosis.confidence,
            "provider": diagnosis.provider,
        }
        if diagnosis
        else None,
        "plan": {
            "id": plan.id,
            "kind": plan.kind,
            "status": plan.status,
            "parameters": plan.parameters,
            "attempts": plan.attempts,
        }
        if plan
        else None,
        "events": [
            {"kind": e.kind, "detail": e.detail, "created_at": e.created_at} for e in events
        ],
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/worker/observe", dependencies=[Depends(worker)])
def observe(data: Observation, db: Session = Depends(get_session)):
    if data.name not in settings.allowed_names:
        raise HTTPException(403, "Container is not registered")
    container = db.get(Container, data.id)
    previous_fault = container is not None and (
        container.health == "unhealthy" or container.status in {"exited", "dead"}
    )
    if container is None:
        previous = db.scalar(select(Container).where(Container.name == data.name))
        if previous is not None:
            db.delete(previous)
            db.flush()
        container = Container(id=data.id, name=data.name)
        db.add(container)
    container.name, container.image, container.status, container.health, container.logs = (
        data.name,
        data.image,
        data.status,
        data.health,
        data.logs,
    )
    from app.models import utcnow

    container.last_seen = utcnow()
    fault = (
        data.status in {"exited", "dead"} and data.exit_code != 0
    ) or data.health == "unhealthy"
    container.failure_streak = min((container.failure_streak or 0) + 1, 1000) if fault else 0
    active = db.scalar(
        select(Incident)
        .where(Incident.container_id == data.id, Incident.status.in_(OPEN))
        .order_by(Incident.id.desc())
    )
    latest = db.scalar(
        select(Incident).where(Incident.container_id == data.id).order_by(Incident.id.desc())
    )
    if fault and active is None and previous_fault and latest and latest.status == "failed":
        db.commit()
        return {"incident_id": latest.id, "created": False}
    if fault and active is None:
        incident = Incident(
            container_id=data.id,
            container_name=data.name,
            image=data.image,
            exit_code=data.exit_code,
            fingerprint=f"{data.id}:fault",
            logs=data.logs,
        )
        db.add(incident)
        db.flush()
        event(
            db,
            incident,
            "detected",
            f"status={data.status}, health={data.health}, exit={data.exit_code}",
        )
        from app.graph import DIAGNOSTIC_GRAPH

        graph_state = DIAGNOSTIC_GRAPH.invoke(
            {"logs": data.logs, "status": data.status, "health": data.health}
        )
        diagnosis = graph_state["diagnosis"]
        db.add(Diagnosis(incident_id=incident.id, **diagnosis))
        incident.status = IncidentStatus.PROPOSED.value
        event(db, incident, "diagnosed", diagnosis["cause"])
        if data.status in {"exited", "dead"} or data.health == "unhealthy":
            db.add(
                RemediationPlan(
                    incident_id=incident.id, kind="restart", parameters={"container_id": data.id}
                )
            )
        db.flush()
        maybe_auto_approve(db, incident, container)
        db.commit()
        return {"incident_id": incident.id, "created": True}
    if (
        not fault
        and active is not None
        and active.status in {"detected", "proposed", "awaiting_approval"}
    ):
        active.status = IncidentStatus.RESOLVED.value
        event(db, active, "recovered", "Container returned to healthy state without remediation")
        pending = db.scalars(
            select(RemediationPlan).where(RemediationPlan.incident_id == active.id)
        ).all()
        for plan in pending:
            if plan.status in {"proposed", "approved"}:
                plan.status = "cancelled"
    if fault and active is not None:
        maybe_auto_approve(db, active, container)
    db.commit()
    return {"incident_id": active.id if active else None, "created": False}


@app.get("/api/dashboard", dependencies=[Depends(admin)])
def dashboard(db: Session = Depends(get_session)):
    containers = db.scalars(select(Container)).all()
    return {
        "total": len(containers),
        "healthy": sum(
            not stale(c) and c.status == "running" and c.health != "unhealthy" for c in containers
        ),
        "unhealthy": sum(
            stale(c) or c.status != "running" or c.health == "unhealthy" for c in containers
        ),
        "monitor_online": any(not stale(c) for c in containers),
        "open_incidents": db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status.in_(OPEN))
        ),
        "recovered": db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status == "resolved")
        ),
        "failed": db.scalar(
            select(func.count()).select_from(Incident).where(Incident.status == "failed")
        ),
    }


@app.get("/api/containers", dependencies=[Depends(admin)])
def containers(db: Session = Depends(get_session)):
    return [
        {
            "id": c.id,
            "name": c.name,
            "image": c.image,
            "status": "stale" if stale(c) else c.status,
            "health": c.health,
            "logs": c.logs,
            "last_seen": c.last_seen,
        }
        for c in db.scalars(select(Container)).all()
    ]


@app.get("/api/incidents", dependencies=[Depends(admin)])
def incidents(db: Session = Depends(get_session)):
    return [
        serialize_incident(db, i)
        for i in db.scalars(select(Incident).order_by(Incident.id.desc()).limit(100)).all()
    ]


@app.get("/api/incidents/{incident_id}", dependencies=[Depends(admin)])
def incident_detail(incident_id: int, db: Session = Depends(get_session)):
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404)
    return serialize_incident(db, incident)


@app.get("/api/settings", dependencies=[Depends(admin)])
def public_settings():
    return {
        "managed_containers": sorted(settings.allowed_names),
        "auto_restart": settings.healops_auto_restart,
        "auto_approve_names": sorted(settings.auto_approve_names),
        "restart_limit": settings.healops_restart_limit,
        "llm_configured": bool(
            settings.llm_base_url and settings.llm_model and settings.llm_api_key
        ),
        "github_connected": False,
        "mode": "read-only until per-plan approval",
    }


@app.post("/api/plans/{plan_id}/decision", dependencies=[Depends(admin)])
def decide(plan_id: int, approved: bool, db: Session = Depends(get_session)):
    plan = db.get(RemediationPlan, plan_id)
    if not plan or plan.status != "proposed":
        raise HTTPException(409, "Plan not pending")
    incident = db.get(Incident, plan.incident_id)
    if incident.status not in {"proposed", "awaiting_approval"}:
        raise HTTPException(409, "Incident not pending")
    plan.status = "approved" if approved else "rejected"
    incident.status = "awaiting_approval" if approved else "failed"
    db.add(Approval(plan_id=plan.id, approved=approved))
    event(db, incident, "approved" if approved else "rejected")
    db.commit()
    return {"status": plan.status}


@app.post("/api/worker/claim", dependencies=[Depends(worker)])
def claim(db: Session = Depends(get_session)):
    if not settings.healops_auto_restart:
        return {"plan": None}
    plan = db.scalar(
        select(RemediationPlan)
        .where(RemediationPlan.status == "approved", RemediationPlan.kind == "restart")
        .order_by(RemediationPlan.id)
    )
    if plan is None:
        return {"plan": None}
    approval = db.scalar(
        select(Approval).where(Approval.plan_id == plan.id, Approval.approved.is_(True))
    )
    if approval is None or plan.attempts >= settings.healops_restart_limit:
        return {"plan": None}
    incident = db.get(Incident, plan.incident_id)
    if incident.status != "awaiting_approval":
        plan.status = "cancelled"
        db.commit()
        return {"plan": None}
    changed = db.execute(
        update(RemediationPlan)
        .where(RemediationPlan.id == plan.id, RemediationPlan.status == "approved")
        .values(status="running", attempts=plan.attempts + 1)
    ).rowcount
    if not changed:
        db.rollback()
        return {"plan": None}
    incident.status = "repairing"
    event(db, incident, "repairing")
    db.commit()
    return {
        "plan": {"id": plan.id, "kind": "restart", "container_id": plan.parameters["container_id"]}
    }


@app.post("/api/worker/plans/{plan_id}/result", dependencies=[Depends(worker)])
def record_result(plan_id: int, result: Result, db: Session = Depends(get_session)):
    plan = db.get(RemediationPlan, plan_id)
    if not plan or plan.status != "running":
        raise HTTPException(409, "Plan not running")
    incident = db.get(Incident, plan.incident_id)
    if result.outcome not in {"success", "failed"}:
        raise HTTPException(422, "Invalid outcome")
    execution = RemediationExecution(plan_id=plan_id, outcome=result.outcome, detail=result.detail)
    db.add(execution)
    db.flush()
    db.add(
        VerificationResult(execution_id=execution.id, healthy=result.healthy, detail=result.detail)
    )
    incident.status = "resolved" if result.outcome == "success" and result.healthy else "failed"
    plan.status = "completed" if incident.status == "resolved" else "failed"
    event(
        db,
        incident,
        "verified" if incident.status == "resolved" else "verification_failed",
        result.detail,
    )
    db.commit()
    return {"status": incident.status}
