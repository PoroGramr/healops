# Architecture

```text
browser (admin token in tab session) ── localhost:8088 ── nginx ── FastAPI ── SQLite volume
                                                          ↑
                                      worker token ── Docker worker ── docker.sock
                                                              │
                                                     explicit demo allowlist
```

Worker subscribes to allowlist-filtered Docker container events to wake its observer and also reconciles allowlisted containers every five seconds (status, Docker Health, exit code, and last 80 log lines). Events are hints, not independent authorization; polling catches missed events. The worker posts normalized snapshots. The API deduplicates active incidents by container ID. It records observations, diagnosis, approval events and execution/verification results in SQLite via SQLAlchemy. Alembic creates the schema on startup. Incident/plan status transitions are checked at decision/claim/result boundaries. The worker has no LLM credentials; the API has no Docker socket. An optional LLM request times out after 8 seconds and falls back to rules. LangGraph runs the bounded context → classification → diagnosis → deterministic proposal → validation → request-approval route, and stops there. After explicit admin approval, a separately enabled worker can claim only a restart plan and verify Docker running/health twice around a stability window.

This is a Docker-only MVP. There is no metrics/deployment-history ingestion, Kubernetes plugin implementation, Codex worktree adapter, PR, redeployment, or rollback yet. A Docker/Kubernetes adapter boundary, when added, must expose observations and an allowlisted remediation protocol, never arbitrary shell execution.
