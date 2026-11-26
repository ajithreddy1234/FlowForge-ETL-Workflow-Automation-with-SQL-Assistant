import httpx
import pytest

import api.sql_assistant_service as assistant

OK = {"choices": [{"message": {"content": "```sql\nSELECT 1\n```"}}]}


@pytest.fixture(autouse=True)
def hosted(monkeypatch):
    monkeypatch.setattr(assistant, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(assistant.time, "sleep", lambda seconds: None)


def _provider(monkeypatch, responses):
    calls = []

    def post(*args, **kwargs):
        calls.append(kwargs["json"]["model"])
        status, payload, headers = responses.pop(0)
        if isinstance(payload, dict):
            return httpx.Response(status, json=payload, headers=headers)
        return httpx.Response(status, text=payload, headers=headers)

    monkeypatch.setattr(assistant.httpx, "post", post)
    return calls


def test_rate_limits_and_server_errors_are_retried(monkeypatch):
    calls = _provider(monkeypatch, [(429, "slow down", {}), (503, "busy", {}), (200, OK, {})])
    assert assistant._hosted_sql("q", "postgresql", "", []) == "SELECT 1"
    assert len(calls) == 3


def test_daily_free_limit_stops_immediately(monkeypatch):
    calls = _provider(monkeypatch, [(429, "Rate limit exceeded: free-models-per-day", {})])
    with pytest.raises(assistant.SqlAssistantUnavailable, match="daily request limit"):
        assistant._hosted_sql("q", "postgresql", "", [])
    assert len(calls) == 1


def test_persistent_rate_limit_gives_up(monkeypatch):
    attempts = assistant.LLM_RATE_LIMIT_RETRIES + 1
    calls = _provider(monkeypatch, [(429, "slow down", {})] * attempts)
    with pytest.raises(assistant.SqlAssistantUnavailable, match="rate limiting"):
        assistant._hosted_sql("q", "postgresql", "", [])
    assert len(calls) == attempts


def test_invalid_key_is_not_retried(monkeypatch):
    calls = _provider(monkeypatch, [(401, "bad key", {})])
    with pytest.raises(assistant.SqlAssistantUnavailable, match="rejected"):
        assistant._hosted_sql("q", "postgresql", "", [])
    assert len(calls) == 1


def test_retry_after_header_is_honoured_and_capped():
    assert assistant._retry_after_seconds(httpx.Response(429, headers={"retry-after": "7"}), 0) == 7
    assert assistant._retry_after_seconds(httpx.Response(429, headers={"retry-after": "999"}), 0) == 60
    assert assistant._retry_after_seconds(httpx.Response(429), 2) == 20


def test_self_correction_feedback_reaches_the_model(monkeypatch):
    seen = []

    def post(*args, **kwargs):
        seen.append(kwargs["json"]["messages"][-1]["content"])
        return httpx.Response(200, json=OK)

    monkeypatch.setattr(assistant.httpx, "post", post)
    assistant._hosted_sql("q", "postgresql", "TABLE public.t (id int);", ["Your SQL:\nSELECT x\nwas rejected: bad"])
    assert "was rejected: bad" in seen[0] and "Write a corrected query." in seen[0]
