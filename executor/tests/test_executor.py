from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from healops_executor.main import RestartPolicy

GOOD_ID = "a" * 64


def fake_container(name="healops-broken-app", project="deploy"):
    container = Mock()
    container.id = GOOD_ID
    container.name = name
    container.labels = {
        "com.docker.compose.project": project,
        "com.docker.compose.service": "broken-app",
    }
    container.image.tags = ["deploy-broken-app:latest"]
    container.attrs = {"Config": {"Image": "deploy-broken-app"}}
    return container


def policy(container):
    return RestartPolicy(
        SimpleNamespace(containers=SimpleNamespace(get=lambda _: container)),
        "healops-broken-app",
        "deploy",
        "broken-app",
        "deploy-broken-app",
        limit=1,
        window=3600,
    )


def test_allowlisted_restart_and_circuit():
    container = fake_container()
    target = policy(container)
    target.restart(GOOD_ID)
    container.restart.assert_called_once_with(timeout=10)
    with pytest.raises(RuntimeError, match="circuit"):
        target.restart(GOOD_ID)
    container.restart.assert_called_once()


@pytest.mark.parametrize(
    "container_id,container",
    [
        ("invalid", fake_container()),
        (GOOD_ID, fake_container(name="production-db")),
        (GOOD_ID, fake_container(project="wrong-project")),
    ],
)
def test_reject_wrong_identity(container_id, container):
    with pytest.raises(ValueError):
        policy(container).restart(container_id)
    container.restart.assert_not_called()
