import os
import queue
import threading
import time

import docker
import httpx

from healops_worker.monitor import managed, normalize


def event_listener(client, names: set[str], wake: threading.Event, events=None):
    """Events only trigger a new poll; they never directly authorize a Docker action."""
    while True:
        try:
            stream = client.events(
                decode=True, filters={"type": "container", "container": sorted(names)}
            )
            for item in stream:
                actor_name = (item.get("Actor") or {}).get("Attributes", {}).get("name")
                if actor_name in names:
                    if events is not None:
                        try:
                            events.put_nowait(item)
                        except queue.Full:
                            pass  # Polling catches persistent failures.
                    wake.set()
            time.sleep(3)
        except docker.errors.DockerException as exc:
            print(f"event stream reconnecting: {type(exc).__name__}", flush=True)
            time.sleep(3)


def execute_restart(client, plan: dict, names: set[str]) -> dict:
    if plan.get("kind") != "restart" or set(plan) != {"id", "kind", "container_id"}:
        raise ValueError("Unsupported remediation")
    container = client.containers.get(plan["container_id"])
    if container.name not in names or container.id != plan["container_id"]:
        raise ValueError("Container not registered")
    container.restart(timeout=10)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        container.reload()
        state = container.attrs.get("State", {})
        health = (state.get("Health") or {}).get("Status", "none")
        if state.get("Status") == "running" and health in {"healthy", "none"}:
            # Stability window; avoids reporting an immediately-crashing app healthy.
            time.sleep(3)
            container.reload()
            state = container.attrs.get("State", {})
            health = (state.get("Health") or {}).get("Status", "none")
            if state.get("Status") == "running" and health in {"healthy", "none"}:
                return {
                    "outcome": "success",
                    "healthy": True,
                    "detail": "Container running after stability window",
                }
        time.sleep(2)
    return {
        "outcome": "failed",
        "healthy": False,
        "detail": "Health check did not recover within 30s",
    }


def probe_http(url: str) -> bool:
    """A configured Spring Actuator health endpoint must explicitly report UP."""
    try:
        with httpx.Client(timeout=3.0) as client:
            result = client.get(url)
            body = result.json()
            return (
                result.status_code == 200
                and isinstance(body, dict)
                and body.get("status") == "UP"
            )
    except (httpx.HTTPError, ValueError):
        return False


def run_once(
    client,
    api: httpx.Client,
    names: set[str],
    auto_restart: bool,
    health_urls: dict[str, str] | None = None,
    capture_logs: bool = True,
    events=None,
):
    if events is not None:
        while True:
            try:
                item = events.get_nowait()
            except queue.Empty:
                break
            attributes = (item.get("Actor") or {}).get("Attributes") or {}
            name = attributes.get("name")
            action = item.get("Action", "")
            if name not in names or action not in {"die", "health_status: unhealthy"}:
                continue
            try:
                exit_code = (
                    int(attributes.get("exitCode", 0)) if action == "die" else None
                )
            except (TypeError, ValueError):
                exit_code = None
            api.post(
                "/api/worker/observe",
                json={
                    "id": item.get("id", ""),
                    "name": name,
                    "status": "exited" if action == "die" else "running",
                    "health": "none" if action == "die" else "unhealthy",
                    "exit_code": exit_code,
                },
            ).raise_for_status()
    for container in managed(client, names):
        try:
            snapshot = normalize(container, include_logs=capture_logs)
            if (
                health_urls
                and container.name in health_urls
                and snapshot["status"] == "running"
            ):
                snapshot["health"] = (
                    "healthy"
                    if probe_http(health_urls[container.name])
                    else "unhealthy"
                )
            api.post("/api/worker/observe", json=snapshot).raise_for_status()
        except (docker.errors.DockerException, httpx.HTTPError) as exc:
            print(
                f"observation failed for {container.name}: {type(exc).__name__}",
                flush=True,
            )
    if auto_restart:
        response = api.post("/api/worker/claim")
        response.raise_for_status()
        plan = response.json().get("plan")
        if plan:
            try:
                result = execute_restart(client, plan, names)
            except (docker.errors.DockerException, ValueError) as exc:
                result = {
                    "outcome": "failed",
                    "healthy": False,
                    "detail": type(exc).__name__,
                }
            api.post(
                f"/api/worker/plans/{plan['id']}/result", json=result
            ).raise_for_status()


def main():
    names = {
        n.strip()
        for n in os.getenv("HEALOPS_MANAGED_CONTAINERS", "healops-broken-app").split(
            ","
        )
        if n.strip()
    }
    token = os.environ["HEALOPS_WORKER_TOKEN"]
    auto_restart = os.getenv("HEALOPS_AUTO_RESTART", "false").lower() == "true"
    health_name = os.getenv("HEALOPS_HTTP_HEALTH_CONTAINER", "")
    health_url = os.getenv("HEALOPS_HTTP_HEALTH_URL", "")
    if bool(health_name) != bool(health_url) or (
        health_name and health_name not in names
    ):
        raise ValueError("HTTP health probe must target one registered container")
    health_urls = {health_name: health_url} if health_name else {}
    capture_logs = os.getenv("HEALOPS_CAPTURE_LOGS", "true").lower() == "true"
    client = docker.from_env()
    wake = threading.Event()
    events = queue.Queue(maxsize=128)
    threading.Thread(
        target=event_listener, args=(client, names, wake, events), daemon=True
    ).start()
    with httpx.Client(
        base_url=os.getenv("HEALOPS_API_URL", "http://127.0.0.1:8000"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=12,
    ) as api:
        while True:
            try:
                run_once(
                    client, api, names, auto_restart, health_urls, capture_logs, events
                )
            except (httpx.HTTPError, docker.errors.DockerException) as exc:
                print(f"poll failed: {type(exc).__name__}", flush=True)
            wake.wait(timeout=5)
            wake.clear()


if __name__ == "__main__":
    main()
