import os
import time

import docker
import httpx

from healops_worker.monitor import managed, normalize


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


def run_once(client, api: httpx.Client, names: set[str], auto_restart: bool):
    for container in managed(client, names):
        try:
            api.post(
                "/api/worker/observe", json=normalize(container)
            ).raise_for_status()
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
    client = docker.from_env()
    with httpx.Client(
        base_url=os.getenv("HEALOPS_API_URL", "http://127.0.0.1:8000"),
        headers={"Authorization": f"Bearer {token}"},
        timeout=12,
    ) as api:
        while True:
            try:
                run_once(client, api, names, auto_restart)
            except (httpx.HTTPError, docker.errors.DockerException) as exc:
                print(f"poll failed: {type(exc).__name__}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
