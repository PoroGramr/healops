# HealOps agent guide

This repository is an experimental Docker-only MVP. Read `README.md`, `docs/architecture.md`, and `docs/security.md` before modifying operations or claiming features are complete. Kubernetes, Codex patch proposals, PR creation, redeployment, and rollback are not implemented.

## Layout

- `backend/app/`: FastAPI endpoints, SQLAlchemy models, Alembic-backed persistence, bounded LangGraph diagnosis. The API has no Docker socket.
- `worker/healops_worker/`: Docker SDK observer and the only Docker-socket client. Docker Events trigger reconciliation; periodic polling covers missed events.
- `frontend/src/`: React/Vite dashboard consuming authenticated `/api` endpoints. Data is live unless explicitly labeled otherwise.
- `deploy/docker-compose.yml`: localhost-only development stack. `examples/broken-app/` is the disposable fault-injection target.

## Non-negotiable boundaries

- Default to read-only monitoring. Never mount Docker socket in API/frontend or expose the dashboard to the internet by default. A socket-mounted worker is still effectively host-privileged; use a disposable daemon or VM, not a production host.
- Act only on explicitly registered container names. Never execute model-suggested shell commands or edit running container files. Model output is advisory; deterministic code selects structured actions.
- A restart requires both `HEALOPS_AUTO_RESTART=true` and an administrator-approved plan. Do not bypass either gate. Do not add a deploy/PR action without explicit remote-change approval, isolated worktree/tests, and authorization checks.
- Do not commit `.env`, keys, tokens, runtime databases, build artifacts or logs. Do not print credentials in tests or tool output. Treat application logs sent to an LLM as potentially sensitive.
- Keep README and roadmap truthful: a schema/table or UI placeholder does not make deployment, rollback, or Kubernetes functional.

## Verification before committing

```bash
python3 -m venv .venv
.venv/bin/pip install -e './backend[test]' -e './worker[test]'
.venv/bin/ruff check backend/app backend/alembic worker/healops_worker examples/broken-app --select E,F
.venv/bin/pytest -q backend/tests worker/tests
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend test
docker compose -f deploy/docker-compose.yml config --quiet
```

Before `git commit`, inspect `git diff --cached --check` and staged file names. For live demos, verify API auth boundaries, trigger only `healops-broken-app`, and stop the stack after testing on a shared host. Never call untested changes complete or push them to `main` without the user's approval.
