# HealOps

**AI-powered self-healing infrastructure — Docker MVP.** Detect failed containers, explain likely causes, and offer an administrator-controlled restart. Kubernetes support is on the roadmap, not shipped. [한국어 README](README.ko.md)

> **Experimental.** Do not connect the worker to a Docker daemon hosting production containers. The Docker socket has host-level authority; the allowlist is application-level, not a security boundary. This demo is bound to localhost and starts in read-only mode.

For an always-on PW3 monitor on a shared Docker host, use the separate socket-proxy profile in [continuous monitor setup](docs/continuous-monitor.md). Its optional repair overlay enables bounded restart of exactly one approved Compose service via a separate executor; it does not patch or deploy code.

## What works today

- Docker Events wakeup plus five-second reconciliation of an explicit container allowlist: status, exit codes, health checks and recent logs. Active incident deduplication and SQLite audit events.
- LangGraph diagnosis subgraph with rules fallback; optional OpenAI-compatible LLM via `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. The model never selects or executes commands.
- React/Vite dark dashboard with authenticated live statistics, containers, incidents, AI findings, approval queue and runtime settings.
- Explicit administrator approval and an **additional default-off restart switch** before the worker can claim a structured Docker restart. Basic Docker health/stability verification.
- Alembic schema, a local broken-app demo, automated Python/React tests and GitHub Actions CI.

**Not operational:** metrics/deployment history, autonomous code repair, real GitHub PR creation, review/merge, redeployment, rollback, Kubernetes adapter. An [experimental worktree/PR adapter](docs/patch-proposals.md) produced a real Codex patch and passed an isolated test on a disposable fixture, but is not wired to incidents; no real PR or deployment was executed. The isolated executor supports bounded restart and HTTP recovery verification only. [Roadmap](docs/roadmap.md) tracks these separately.

An [isolated PW3 staging and image rollback workflow](docs/pw3-staging.md) is available for candidate validation; it does not promote to production. The schema includes reserved deployment and verification models but does not imply working deployment/rollback.

## Architecture

```text
Browser → localhost:8088 nginx → authenticated FastAPI → SQLite
                                    ↑
                         separate worker token
                                    ↑
                        Docker worker → Docker socket
                         (explicit demo allowlist)
```

The API/dashboard do **not** mount Docker socket. The worker has no LLM key. The diagnostic graph stops at human approval; restart execution is a separate deterministic worker action. See [architecture](docs/architecture.md) and [security limitations](docs/security.md).

## Quick Start

On a **disposable Docker host/VM**:

```bash
git clone https://github.com/PoroGramr/healops.git && cd healops
cp .env.example .env && chmod 600 .env
# Edit .env: replace HEALOPS_API_TOKEN and HEALOPS_WORKER_TOKEN
# with distinct random values (e.g. `python3 -c 'import secrets; print(secrets.token_urlsafe(36))'`).
docker compose -f deploy/docker-compose.yml up -d --build
```

Open `http://127.0.0.1:8088` and enter the admin token. Port 8099 hosts the intentionally broken demo app. Never publish either port or the Docker socket. Use an SSH tunnel if accessing a remote disposable VM. See [deployment](docs/deployment.md).

## Demo

```bash
curl http://127.0.0.1:8099/health   # 200
curl http://127.0.0.1:8099/break    # expected 500
# Wait for Docker healthcheck failure; dashboard shows incident and diagnosis.
# No automatic restart in the default read-only configuration.
curl http://127.0.0.1:8099/reset    # health recovers, incident resolves
```

LLM configuration is optional. Without an API key, status monitoring and rule-based diagnosis still work. If you explicitly enable `HEALOPS_AUTO_RESTART=true` on a disposable demo daemon, administrator approval in the dashboard is additionally required for each restart plan.

## Testing

```bash
python3 -m venv .venv
.venv/bin/pip install -e './backend[test]' -e './worker[test]'
.venv/bin/pytest -q backend/tests worker/tests
.venv/bin/ruff check backend/app backend/alembic worker/healops_worker examples/broken-app --select E,F
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend test
docker compose -f deploy/docker-compose.yml config --quiet
```

## Contributing / License

Open an issue before large changes, add tests, and never commit secrets or runtime data. Apache License 2.0 — see [LICENSE](LICENSE).
