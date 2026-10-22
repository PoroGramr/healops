import json

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.settings import settings


class Answer(BaseModel):
    cause: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(min_length=1, max_length=5)
    confidence: float = Field(ge=0, le=1)


def rule_diagnosis(logs: str, status: str, health: str) -> dict:
    if "Traceback" in logs or "Exception" in logs:
        cause = "Application exception detected in recent logs"
    elif health == "unhealthy":
        cause = "Docker health check is failing"
    else:
        cause = f"Container terminated unexpectedly ({status})"
    return {
        "cause": cause,
        "evidence": [logs[-300:] if logs else f"status={status}, health={health}"],
        "confidence": 0.5,
        "provider": "rules",
    }


def parse_response(raw: str) -> dict:
    parsed = Answer.model_validate(json.loads(raw))
    return {**parsed.model_dump(), "provider": "openai-compatible"}


def diagnose(logs: str, status: str, health: str) -> dict:
    fallback = rule_diagnosis(logs, status, health)
    if not (settings.llm_base_url and settings.llm_model and settings.llm_api_key):
        return fallback
    try:
        with httpx.Client(timeout=8.0) as client:
            result = client.post(
                settings.llm_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "temperature": 0,
                    "max_tokens": 350,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Diagnose Docker failure. Return only JSON with cause (string), "
                                "evidence (1-5 strings), confidence (0-1). Never propose commands."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"status={status} health={health}\nlogs:\n{logs[-4000:]}",
                        },
                    ],
                },
            )
            result.raise_for_status()
            return parse_response(result.json()["choices"][0]["message"]["content"])
    except (httpx.HTTPError, ValueError, KeyError, IndexError, ValidationError):
        return fallback
