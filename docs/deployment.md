# Deployment (local development only)

Requirements: Docker Compose v2, Git, Python >=3.11, Node >=22. This compose file binds HTTP only to `127.0.0.1`; it must not be published to the internet. Docker socket access remains host-level authority even in a separate worker. Run only on a disposable/test Docker daemon or VM. **Do not use on a daemon hosting production containers.**

```bash
git clone https://github.com/PoroGramr/healops.git
cd healops
cp .env.example .env
chmod 600 .env
# Replace BOTH token values with independent random values; never use the example placeholders.
python3 -c 'import secrets; print(secrets.token_urlsafe(36))'
docker compose -f deploy/docker-compose.yml up -d --build
```

Visit `http://127.0.0.1:8088` and enter the admin token from your private `.env`. The demo server is at `http://127.0.0.1:8099`. Dashboard authentication stays in browser sessionStorage for the current tab. The worker receives a separate token. API binds only inside the private Compose network; frontend nginx proxies `/api`. To reach a remote host, use an SSH tunnel (e.g. `ssh -L 8088:127.0.0.1:8088 user@host`). Do not expose port 8088 through a public reverse proxy.

## Safe demo

```bash
curl http://127.0.0.1:8099/health   # healthy
curl http://127.0.0.1:8099/break    # intentional HTTP 500, prints a demo exception
# Wait about 10-20 seconds; the container health becomes unhealthy.
# An incident, rule-based diagnosis, and proposed restart appear in the dashboard.
# Default is READ ONLY; nothing is restarted by the worker.
curl http://127.0.0.1:8099/reset    # remove fault, incident auto-resolves
```

To exercise a restart deliberately on this disposable demo only: set `HEALOPS_AUTO_RESTART=true`, recreate API and worker, trigger `/break`, approve the proposed plan in the dashboard, and inspect recovery. Never approve a restart of another container. `HEALOPS_MANAGED_CONTAINERS` limits the worker and API to explicit names. No unapproved deployment or source change is implemented.

LLM diagnosis is optional: set `LLM_BASE_URL` to an OpenAI-compatible API base ending in `/v1`, `LLM_API_KEY`, and `LLM_MODEL` in `.env`, then recreate API. If unavailable, bounded rule diagnosis continues. Logs may contain sensitive application content; test with sanitized demo data only.

## Local tests

```bash
python3 -m venv .venv
.venv/bin/pip install -e './backend[test]' -e './worker[test]'
.venv/bin/pytest -q backend/tests worker/tests
.venv/bin/ruff check backend/app backend/alembic worker/healops_worker examples/broken-app --select E,F
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend test
```

API migrations are run via `alembic upgrade head` at container startup. Runtime DB persists in named volume `deploy_healops-data`. `docker compose -f deploy/docker-compose.yml down` stops the demo but preserves data; `down -v` erases data. No external resources are required for the rule-based demo.
