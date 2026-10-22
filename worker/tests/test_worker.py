from types import SimpleNamespace
from unittest.mock import Mock, patch
from queue import Queue

import pytest

from healops_worker.main import event_listener, execute_restart, probe_http, run_once
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


def test_http_probe_requires_actuator_up():
    for status, payload, expected in (
        (200, {"status": "UP"}, True),
        (200, {"status": "DOWN"}, False),
        (503, {"status": "DOWN"}, False),
    ):
        with patch("healops_worker.main.httpx.Client") as client:
            client.return_value.__enter__.return_value.get.return_value.status_code = (
                status
            )
            client.return_value.__enter__.return_value.get.return_value.json.return_value = payload
            assert probe_http("http://pw3-attendance:8080/actuator/health") is expected


def test_http_probe_marks_registered_container_unhealthy():
    container = Mock()
    container.id = "abc"
    container.name = "pw3-attendance"
    container.attrs = {"State": {"Status": "running", "ExitCode": 0}}
    container.logs.return_value = b""
    docker_client = SimpleNamespace(containers=SimpleNamespace(get=lambda _: container))
    api = Mock()
    with patch("healops_worker.main.probe_http", return_value=False):
        run_once(
            docker_client,
            api,
            {"pw3-attendance"},
            False,
            {"pw3-attendance": "http://pw3-attendance:8080/actuator/health"},
        )
    assert api.post.call_args.kwargs["json"]["health"] == "unhealthy"


def test_die_event_is_recorded_even_if_container_already_restarted():
    container = Mock()
    container.id = "abc"
    container.name = "pw3-attendance"
    container.attrs = {"State": {"Status": "running", "ExitCode": 0}}
    container.logs.return_value = b""
    docker_client = SimpleNamespace(containers=SimpleNamespace(get=lambda _: container))
    events = Queue()
    events.put(
        {
            "id": "abc",
            "Action": "die",
            "Actor": {"Attributes": {"name": "pw3-attendance", "exitCode": "137"}},
        }
    )
    api = Mock()
    run_once(
        docker_client, api, {"pw3-attendance"}, False, capture_logs=False, events=events
    )
    assert api.post.call_args_list[0].kwargs["json"]["exit_code"] == 137
    assert api.post.call_args_list[0].kwargs["json"]["status"] == "exited"
    assert api.post.call_args_list[1].kwargs["json"]["status"] == "running"


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
    assert normalize(container, include_logs=False)["logs"] == ""
    assert container.logs.call_count == 1


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
