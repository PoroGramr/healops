"""Narrow Docker action endpoint. It alone mounts the raw socket.

A compromised executor remains host-privileged; keep its network private and
never expose a port to the host. Caller cannot supply commands or target names.
"""

import hmac
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import docker

ID = re.compile(r"^[a-f0-9]{64}$")


class RestartPolicy:
    def __init__(
        self,
        client,
        name: str,
        project: str,
        service: str,
        image: str,
        limit: int = 2,
        window: int = 3600,
    ):
        if not all((name, project, service, image)):
            raise ValueError("Exact container identity is required")
        self.client, self.name, self.project, self.service, self.image = (
            client,
            name,
            project,
            service,
            image,
        )
        self.limit, self.window = limit, window
        self.history: list[float] = []
        self.lock = threading.Lock()

    def restart(self, container_id: str) -> None:
        if not ID.fullmatch(container_id):
            raise ValueError("Invalid container ID")
        with self.lock:
            now = time.monotonic()
            self.history = [t for t in self.history if now - t < self.window]
            if len(self.history) >= self.limit:
                raise RuntimeError("Restart circuit open")
            container = self.client.containers.get(self.name)
            labels = container.labels or {}
            if (
                container.id != container_id
                or container.name != self.name
                or labels.get("com.docker.compose.project") != self.project
                or labels.get("com.docker.compose.service") != self.service
                or container.attrs.get("Config", {}).get("Image") != self.image
            ):
                raise ValueError("Container identity mismatch")
            self.history.append(now)  # A failed call still consumes the attempt.
            container.restart(timeout=10)


class Handler(BaseHTTPRequestHandler):
    policy: RestartPolicy
    token: str

    def do_POST(self):
        if self.path != "/restart" or not hmac.compare_digest(
            self.headers.get("Authorization", ""), "Bearer " + self.token
        ):
            self.respond(403, "Forbidden")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 256:
                raise ValueError("Invalid request length")
            body = json.loads(self.rfile.read(length))
            if set(body) != {"container_id"} or not isinstance(
                body["container_id"], str
            ):
                raise ValueError("Unsupported action")
            self.policy.restart(body["container_id"])
        except (ValueError, RuntimeError, docker.errors.DockerException) as exc:
            self.respond(409, type(exc).__name__)
            return
        self.respond(200, "Restarted")

    def do_GET(self):
        self.respond(404, "Not found")

    def respond(self, status: int, message: str):
        content = json.dumps({"result": message}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        # Never log authorization headers, IDs, or request bodies.
        pass


def main():
    token = os.environ["HEALOPS_EXECUTOR_TOKEN"]
    if len(token) < 32:
        raise ValueError("Executor token must be at least 32 characters")
    Handler.token = token
    Handler.policy = RestartPolicy(
        docker.from_env(timeout=15),
        os.environ["HEALOPS_EXECUTOR_CONTAINER"],
        os.environ["HEALOPS_EXECUTOR_PROJECT"],
        os.environ["HEALOPS_EXECUTOR_SERVICE"],
        os.environ["HEALOPS_EXECUTOR_IMAGE"],
    )
    ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()


if __name__ == "__main__":
    main()
