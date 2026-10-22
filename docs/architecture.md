# Architecture

```text
browser (admin token in tab session) ─ localhost:8088 ─ nginx ─ FastAPI ─ SQLite volume
                                                          ↑
worker token ─ GET-only socket proxy ─ Docker worker ─ exact PW3 allowlist + Actuator
                                            │
                           private action network + distinct token
                                            ↓
                                  exact-service executor ─ Docker socket
```

The PW3 worker subscribes to allowlist-filtered Docker Events and reconciles container status and HTTP Actuator health every five seconds. The API records incidents, diagnosis, policy approvals, execution and verification in SQLite. Production log capture is disabled. A planned PW3 deployment writes a short-lived host maintenance marker mounted read-only into the worker; events during that window are discarded. Healthy replacement observations close pending incidents tied to the old container ID. The API has no Docker socket; only the executor owns the full socket and validates exact container identity before bounded restart.

A separate opt-in Codex adapter runs inside an ephemeral Docker sandbox against a temporary Git worktree. The PW3 profile limits changed files to registered Java source/test paths, runs Gradle/Playwright offline in a second networkless test image, builds a candidate artifact and exercises image rollout/rollback on isolated MySQL/MinIO staging. It can propose a GitHub PR, but is **not** connected to production incidents or automatic PR merge. PW3's own Actions workflow deploys `main` with health-gated image/env/Compose rollback; database migrations are not rolled back. HealOps has no automatic production code-promotion controller or Kubernetes plugin.
