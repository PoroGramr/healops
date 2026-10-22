import json
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "staging_rollout", Path(__file__).resolve().parents[2] / "scripts/staging_rollout.py"
)
assert spec is not None and spec.loader is not None
rollout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rollout)

PREVIOUS = "sha256:" + "a" * 64
CANDIDATE = "sha256:" + "b" * 64


def setup_rollout(tmp_path, monkeypatch, checks):
    (tmp_path / ".env.staging").write_text("test-only\n")
    monkeypatch.setattr(rollout, "ROOT", tmp_path)
    calls = []

    def fake_run(*args):
        calls.append(args)
        if args[:3] == ("docker", "image", "inspect"):
            return PREVIOUS if args[3] == rollout.TAG else CANDIDATE
        if args[:2] == ("docker", "inspect"):
            return json.dumps(
                [
                    {
                        "Config": {
                            "Labels": {
                                "com.docker.compose.project": "healops-pw3-stage",
                                "com.docker.compose.service": "app",
                            }
                        }
                    }
                ]
            )
        return ""

    monkeypatch.setattr(rollout, "run", fake_run)
    it = iter(checks)
    monkeypatch.setattr(rollout, "healthy", lambda _: next(it))
    return calls


def test_staging_deployment_success(tmp_path, monkeypatch):
    calls = setup_rollout(tmp_path, monkeypatch, [True, True])
    result = rollout.deploy(CANDIDATE, 10)
    assert result["status"] == "deployed"
    assert ("docker", "image", "tag", CANDIDATE, rollout.TAG) in calls


def test_failed_candidate_restores_previous_image(tmp_path, monkeypatch):
    calls = setup_rollout(tmp_path, monkeypatch, [True, False, True])
    with pytest.raises(RuntimeError, match="previous image restored and verified"):
        rollout.deploy(CANDIDATE, 10)
    assert ("docker", "image", "tag", PREVIOUS, rollout.TAG) in calls
    assert sum("--force-recreate" in c for c in calls) == 2


def test_wrong_target_never_tags_an_image(tmp_path, monkeypatch):
    calls = setup_rollout(tmp_path, monkeypatch, [True])
    orig = rollout.run

    def wrong(*args):
        if args[:2] == ("docker", "inspect"):
            return json.dumps(
                [
                    {
                        "Config": {
                            "Labels": {
                                "com.docker.compose.project": "pw3-production",
                                "com.docker.compose.service": "app",
                            }
                        }
                    }
                ]
            )
        return orig(*args)

    monkeypatch.setattr(rollout, "run", wrong)
    with pytest.raises(RuntimeError, match="Not the isolated"):
        rollout.deploy(CANDIDATE, 10)
    assert not any(c[:3] == ("docker", "image", "tag") for c in calls)
