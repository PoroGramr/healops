from collections.abc import Iterable


def classify(snapshot: dict) -> bool:
    """Docker inspect snapshot -> actionable fault (exit 0 is intentionally ignored)."""
    state = snapshot.get("State") or {}
    health = (state.get("Health") or {}).get("Status", "none")
    return health == "unhealthy" or (
        state.get("Status") in {"exited", "dead"} and state.get("ExitCode") != 0
    )


def normalize(container, include_logs: bool = True) -> dict:
    container.reload()
    attrs = container.attrs
    state = attrs.get("State") or {}
    return {
        "id": container.id,
        "name": container.name,
        "image": attrs.get("Config", {}).get("Image", ""),
        "status": state.get("Status", "unknown"),
        "health": (state.get("Health") or {}).get("Status", "none"),
        "exit_code": state.get("ExitCode"),
        "logs": container.logs(tail=80).decode("utf-8", errors="replace")[-8192:]
        if include_logs
        else "",
    }


def managed(client, names: set[str]) -> Iterable:
    # Never enumerate or mutate containers outside the explicit allowlist.
    for name in sorted(names):
        try:
            yield client.containers.get(name)
        except Exception as exc:
            # Container may not yet exist; leave other names observable.
            if exc.__class__.__name__ != "NotFound":
                raise
