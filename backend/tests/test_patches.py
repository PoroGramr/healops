import subprocess
import json
from dataclasses import replace
from pathlib import Path

import pytest

from app import patches


def git(repo: Path, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    folder = tmp_path / "source"
    folder.mkdir()
    git(folder, "init", "-b", "main")
    git(folder, "config", "user.name", "HealOps Test")
    git(folder, "config", "user.email", "test@example.invalid")
    (folder / "app.py").write_text("BUG = True\n")
    git(folder, "add", "app.py")
    git(folder, "commit", "-m", "baseline")
    (tmp_path / "codex-auth.json").write_text("test-only")
    return folder


def policy(repo, paths=frozenset({"app.py"})):
    return patches.PatchPolicy(
        repo,
        "example/project",
        paths,
        "sha256:" + "a" * 64,
        ("python", "-m", "pytest"),
        "sha256:" + "b" * 64,
        repo.parent / "codex-auth.json",
    )


def fake_external(real, path="app.py"):
    def call(argv, cwd, timeout, input_text=None):
        if argv[:2] == ["docker", "image"]:
            return "sha256:" + "a" * 64
        if argv[:2] == ["docker", "run"]:
            assert "--read-only" in argv and "--cap-drop" in argv
            if "--dangerously-bypass-approvals-and-sandbox" in argv:
                assert "/home/node/.codex/auth.json:ro" in " ".join(argv)
                (cwd / path).write_text("BUG = False\n")
                return "patched"
            assert "none" in argv
            return "1 passed"
        if argv[:3] == ["gh", "pr", "create"]:
            return "https://github.com/example/project/pull/1"
        return real(argv, cwd, timeout, input_text)

    return call


def test_patch_in_worktree_and_networkless_test(repo, monkeypatch):
    monkeypatch.setattr(patches, "command", fake_external(patches.command))
    result = patches.propose_patch(policy(repo), 7, "Bug", ["Traceback"])
    assert result["validated"] and not result["published"]
    assert result["files"] == ["app.py"] and "BUG = False" in result["diff"]
    assert result["test_output"] == "1 passed"
    assert (repo / "app.py").read_text() == "BUG = True\n"
    listing = subprocess.run(
        ["git", "worktree", "list", "--porcelain"], cwd=repo, capture_output=True, text=True
    )
    assert listing.stdout.count("worktree ") == 1


def test_reject_unregistered_change(repo, monkeypatch):
    monkeypatch.setattr(patches, "command", fake_external(patches.command, "unauthorized.py"))
    with pytest.raises(RuntimeError, match="unregistered"):
        patches.propose_patch(policy(repo), 8, "Bug", [])
    assert not (repo / "unauthorized.py").exists()


def test_policy_blocks_path_traversal(repo):
    with pytest.raises(ValueError):
        policy(repo, frozenset({"../.env"})).validate()


def test_publish_branch_then_open_pr_in_isolated_git_fixture(repo, tmp_path, monkeypatch):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(bare))
    monkeypatch.setattr(patches, "command", fake_external(patches.command))
    result = patches.propose_patch(policy(repo), 9, "Bug", [], publish=True)
    assert result["pr_url"] == "https://github.com/example/project/pull/1"
    ref = subprocess.run(
        ["git", "--git-dir", str(bare), "show-ref", "--verify", "refs/heads/healops/incident-9"],
        capture_output=True,
    )
    assert ref.returncode == 0


def test_pw3_candidate_builds_tests_and_stages_before_pr(repo, monkeypatch):
    source = repo / "src/main/java/Fix.java"
    source.parent.mkdir(parents=True)
    source.write_text("class Fix { boolean broken = true; }\n")
    git(repo, "add", "src")
    git(repo, "commit", "-m", "add fixture")
    registered = "src/main/java/Fix.java"
    config = replace(policy(repo, frozenset({registered})), stage_pw3=True)
    real = patches.command

    def fake(argv, cwd, timeout, input_text=None):
        if argv[:2] == ["docker", "image"]:
            return "sha256:" + "a" * 64
        if argv[:2] == ["docker", "run"]:
            if "--dangerously-bypass-approvals-and-sandbox" in argv:
                (cwd / registered).write_text("class Fix { boolean broken = false; }\n")
                return "patched"
            assert "none" in argv and "5g" in argv and "--shm-size" in argv
            mount = next(x for x in argv if x.endswith(":/out:rw"))
            (Path(mount.removesuffix(":/out:rw")) / "app.jar").write_bytes(b"jar fixture")
            return "BUILD SUCCESSFUL"
        if argv[:2] == ["docker", "build"]:
            return "built"
        if len(argv) > 1 and str(argv[1]).endswith("staging_rollout.py"):
            return json.dumps({"status": "deployed", "image": "sha256:" + "a" * 64})
        return real(argv, cwd, timeout, input_text)

    monkeypatch.setattr(patches, "command", fake)
    result = patches.propose_patch(config, 42, "broken boolean", [], publish=False)
    assert result["staging"]["status"] == "deployed"
    assert result["published"] is False
    assert "broken = true" in source.read_text()


def test_pw3_policy_rejects_db_migration(repo):
    config = replace(
        policy(repo, frozenset({"src/main/resources/db/migration/V7__x.sql"})), stage_pw3=True
    )
    with pytest.raises(ValueError, match="migrations"):
        config.validate()
