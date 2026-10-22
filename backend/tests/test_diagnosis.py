import pytest
from pydantic import ValidationError

from app.diagnosis import parse_response, rule_diagnosis
from app.graph import DIAGNOSTIC_GRAPH


def test_llm_json_validation():
    result = parse_response('{"cause":"demo failure","evidence":["traceback"],"confidence":0.8}')
    assert result["provider"] == "openai-compatible"
    for bad in (
        '{"cause":"","evidence":[],"confidence":2}',
        '{"cause": "bad", "evidence": ["x"], "confidence": -1}',
    ):
        with pytest.raises(ValidationError):
            parse_response(bad)


def test_graph_enforces_human_approval():
    result = DIAGNOSTIC_GRAPH.invoke(
        {"logs": "Traceback: Exception", "status": "running", "health": "unhealthy"}
    )
    assert result["diagnosis"]["provider"] == "rules"
    assert result["proposal"] == "restart"
    assert result["next_step"] == "human_approval_required"
    assert rule_diagnosis("", "exited", "none")["provider"] == "rules"


def test_llm_failure_falls_back(monkeypatch):
    from app.diagnosis import diagnose
    from app.settings import settings

    monkeypatch.setattr(settings, "llm_base_url", "http://127.0.0.1:1/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-only-key")
    monkeypatch.setattr(settings, "llm_model", "fake")
    assert diagnose("Exception", "exited", "none")["provider"] == "rules"
