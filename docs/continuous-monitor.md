# Continuous PW3 monitor on a shared Docker host

This is an **always-on observation-only** profile. It detects a failed `pw3-attendance` container or a non-UP HTTP Actuator response; it does **not** automatically restart, patch, redeploy or notify. The existing PW3 Docker `restart: unless-stopped` policy already restarts the process after a crash, but not an unhealthy running application. Autonomous code changes are not available in this MVP.

The worker receives `DOCKER_HOST=tcp://socket-proxy:2375` on a private internal network. It does not mount the host Docker socket. The proxy grants Docker `CONTAINERS`, `EVENTS`, `PING` and `VERSION` GET operations only; `POST=0` blocks every Docker state-changing request. This is not strict per-container read isolation: compromise of the worker could read information about other containers through GET. The API/HTTP dashboard cannot reach the socket network. The worker's HTTP probe reaches PW3 on the existing `web` network. Production log capture is disabled by default to avoid copying secrets into HealOps. Do not publish the proxy port or dashboard beyond localhost.

Create an **ignored** `.env.monitor` with independent administrator and worker tokens, `HEALOPS_MANAGED_CONTAINERS=pw3-attendance`, `HEALOPS_HTTP_HEALTH_CONTAINER=pw3-attendance`, `HEALOPS_HTTP_HEALTH_URL=http://pw3-attendance:8080/actuator/health`, and `HEALOPS_AUTO_RESTART=false` (the Compose file also hard-disables restart). Then:

```bash
docker compose -f deploy/compose.monitor.yml up -d --build
docker compose -f deploy/compose.monitor.yml ps
```

The dashboard is available only on `http://127.0.0.1:8088`. Connect remotely by SSH tunnel: `ssh -L 8088:127.0.0.1:8088 user@server`. Enter the administrator token from `.env.monitor`; never paste it into chat or commit the file. Dashboard and worker refresh every five seconds or on a Docker Event. An actionable Docker `die`/unhealthy event is recorded before reconciliation, so a fast Docker auto-restart is not silently missed. If no fresh worker observation arrives for 20 seconds, the dashboard reports the monitor offline/stale instead of falsely green. `docker compose -f deploy/compose.monitor.yml down` stops only HealOps, leaving PW3 untouched. `restart: unless-stopped` starts the monitor again after Docker/service restarts.

**Not yet self-healing:** a read-only socket proxy cannot execute a restart. Do not set `HEALOPS_AUTO_RESTART=true` and assume it works. A safe automatic restart requires a separately designed, narrowly authorized executor, circuit breaker, verification, and failure handling. Unattended source patch and redeploy additionally require isolated worktree/build/test, deployment provenance and working rollback. Do not present this observation profile as those capabilities. A complete host outage also stops this same-host monitor; external monitoring is required to detect it.
