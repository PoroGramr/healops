from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from healops_worker.main import event_listener, execute_restart
from healops_worker.monitor import classify, normalize


def test_event_classification():
    assert classify({"State": {"Status": "exited", "ExitCode": 1}})
    assert not classify({"State": {"Status": "exited", "ExitCode": 0}})
    assert classify({"State": {"Status": "running", "Health": {"Status": "unhealthy"}}})
    assert not classify(
        {"State": {"Status": "running", "Health": {"Status": "healthy"}}}
    )


def test_event_filter_and_wakeup():
    wake = Mock()

    def stream():
        yield {"Actor": {"Attributes": {"name": "unregistered"}}}
        yield {"Actor": {"Attributes": {"name": "healops-broken-app"}}}
        raise RuntimeError("stop test listener")

    client = Mock()
    client.events.return_value = stream()
    with pytest.raises(RuntimeError, match="stop test listener"):
        event_listener(client, {"healops-broken-app"}, wake)
    client.events.assert_called_once_with(
        decode=True, filters={"type": "container", "container": ["healops-broken-app"]}
    )
    wake.set.assert_called_once()


def test_normalize_health_event():
    container = Mock()
    container.id = "abc"
    container.name = "healops-broken-app"
    container.attrs = {
        "Config": {"Image": "broken:v1"},
        "State": {
            "Status": "running",
            "Health": {"Status": "unhealthy"},
            "ExitCode": 0,
        },
    }
    container.logs.return_value = b"RuntimeError: demo failure"
    result = normalize(container)
    assert result["health"] == "unhealthy"
    assert result["logs"] == "RuntimeError: demo failure"


def test_reject_unregistered_and_commands():
    container = Mock(id="abc", name="production-db")
    client = SimpleNamespace(containers=SimpleNamespace(get=lambda id: container))
    with pytest.raises(ValueError):
        execute_restart(
            client,
            {"id": 1, "kind": "shell", "container_id": "abc"},
            {"healops-broken-app"},
        )
    with pytest.raises(ValueError):
        execute_restart(
            client,
            {"id": 1, "kind": "restart", "container_id": "abc"},
            {"healops-broken-app"},
        )
    container.restart.assert_not_called()


def test_recovery_stability_window():
    container = Mock()
    container.id = "abc"
    container.name = "healops-broken-app"
    container.attrs = {"State": {"Status": "running", "Health": {"Status": "healthy"}}}
    client = SimpleNamespace(containers=SimpleNamespace(get=lambda id: container))
    with patch("healops_worker.main.time.sleep"):
        result = execute_restart(
            client,
            {"id": 1, "kind": "restart", "container_id": "abc"},
            {"healops-broken-app"},
        )
    assert result["healthy"]
    container.restart.assert_called_once_with(timeout=10)
