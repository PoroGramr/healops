"""Deploy a pinned PW3 image to isolated staging, or restore the previous image.

No production Docker Compose file, network, database or hostname is referenced.
"""

import argparse
import fcntl
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    str(ROOT / ".env.staging"),
    "-f",
    str(ROOT / "deploy/compose.pw3-staging.yml"),
]
TAG = "healops-pw3-stage-app:latest"
HEALTH = "http://127.0.0.1:18080/actuator/health"
PAGE = "http://127.0.0.1:18080/qr-display.html"


def run(*argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=150)
    if result.returncode:
        raise RuntimeError(f"{argv[0]} failed (exit {result.returncode})")
    return result.stdout.strip()


def healthy(timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH, timeout=3) as response:
                body = json.load(response)
                if response.status == 200 and body.get("status") == "UP":
                    with urllib.request.urlopen(PAGE, timeout=3) as page:
                        if page.status == 200:
                            return True
        except (OSError, ValueError):
            pass
        time.sleep(2)
    return False


def deploy(candidate: str, timeout: int = 120):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", candidate) or not 5 <= timeout <= 300:
        raise ValueError("Use a pinned image ID and a bounded health timeout")
    if not (ROOT / ".env.staging").is_file():
        raise RuntimeError("Missing isolated staging configuration")
    with (ROOT / ".staging-deploy.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run("docker", "image", "inspect", candidate, "--format", "{{.Id}}")
        previous = run("docker", "image", "inspect", TAG, "--format", "{{.Id}}")
        target = json.loads(run("docker", "inspect", "healops-pw3-stage-app-1"))[0]
        labels = target["Config"]["Labels"]
        if (
            labels.get("com.docker.compose.project") != "healops-pw3-stage"
            or labels.get("com.docker.compose.service") != "app"
        ):
            raise RuntimeError("Not the isolated PW3 staging application")
        if not healthy(5):
            raise RuntimeError("Staging baseline is unhealthy; refusing deployment")
        run("docker", "image", "tag", candidate, TAG)
        try:
            run(
                *COMPOSE,
                "up",
                "-d",
                "--no-build",
                "--no-deps",
                "--force-recreate",
                "app",
            )
            if not healthy(timeout):
                raise RuntimeError("Candidate failed Actuator/page checks")
            return {"status": "deployed", "image": candidate, "previous": previous}
        except Exception as error:
            # A failed compose up may have partially replaced the old app.
            run("docker", "image", "tag", previous, TAG)
            try:
                run(
                    *COMPOSE,
                    "up",
                    "-d",
                    "--no-build",
                    "--no-deps",
                    "--force-recreate",
                    "app",
                )
                if not healthy(120):
                    raise RuntimeError("Previous image failed health verification")
            except Exception as rollback_error:
                raise RuntimeError(
                    f"Deploy failed; rollback FAILED: {rollback_error}"
                ) from error
            raise RuntimeError(
                f"Deploy failed; previous image restored and verified: {error}"
            ) from error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Locally built sha256 image ID")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        print(json.dumps(deploy(args.image, args.timeout)))
    except (RuntimeError, ValueError, BlockingIOError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
