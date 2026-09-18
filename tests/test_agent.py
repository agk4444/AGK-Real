"""Tests for the agent stdlib module (AGK-Real 0.5.0).

The module talks to an OpenAI-compatible /chat/completions endpoint via
urllib. No test here touches the network: urllib.request.urlopen is
mocked, and the API key comes from the environment or explicit args.
"""

import json
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

from agk.pipeline import run_source


def ns():
    _, namespace, warnings = run_source(
        "import agent\ndefine function main:\n    print(\"ok\")\n")
    assert warnings == []
    return namespace


class FakeResponse:
    def __init__(self, body):
        self._body = body.encode("utf-8") if isinstance(body, str) else body

    def read(self):
        return self._body

    def close(self):
        pass


def chat_payload(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}




def model_says(obj):
    """A fake /chat/completions HTTP body whose message content is obj."""
    return FakeResponse(json.dumps(chat_payload(json.dumps(obj))))

def test_chat_parses_reply_text(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "test-key")
    agent = ns()
    with patch.object(urllib.request, "urlopen",
                      return_value=FakeResponse(json.dumps(chat_payload("hello there")))) as m:
        assert agent["chat"]([{"role": "user", "content": "hi"}]) == "hello there"
    req = m.call_args[0][0]
    assert req.full_url == "https://api.openai.com/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer test-key"
    assert req.get_header("Content-type") == "application/json"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "gpt-4o-mini"
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_chat_explicit_key_and_base_url(monkeypatch):
    monkeypatch.delenv("AGK_LLM_API_KEY", raising=False)
    agent = ns()
    with patch.object(urllib.request, "urlopen",
                      return_value=FakeResponse(json.dumps(chat_payload("ok")))) as m:
        out = agent["chat"]([{"role": "user", "content": "hi"}],
                            "my-model", "secret-key", "http://llm.test")
    assert out == "ok"
    req = m.call_args[0][0]
    assert req.full_url == "http://llm.test/chat/completions"
    assert req.get_header("Authorization") == "Bearer secret-key"
    assert json.loads(req.data.decode())["model"] == "my-model"


def test_chat_base_url_from_env(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    monkeypatch.setenv("AGK_LLM_BASE_URL", "http://env.test/v2")
    agent = ns()
    with patch.object(urllib.request, "urlopen",
                      return_value=FakeResponse(json.dumps(chat_payload("ok")))) as m:
        agent["chat"]([{"role": "user", "content": "hi"}])
    assert m.call_args[0][0].full_url == "http://env.test/v2/chat/completions"


def test_chat_missing_key_is_a_clean_error(monkeypatch):
    monkeypatch.delenv("AGK_LLM_API_KEY", raising=False)
    monkeypatch.delenv("AGK_LLM_BASE_URL", raising=False)
    agent = ns()
    with pytest.raises(Exception, match="no API key"):
        agent["chat"]([{"role": "user", "content": "hi"}], "m", "", "")


def test_chat_http_failure_is_a_clean_error(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    agent = ns()
    with patch.object(urllib.request, "urlopen",
                      side_effect=urllib.error.URLError("boom")):
        with pytest.raises(Exception, match=r"agent\.chat: request to .* failed"):
            agent["chat"]([{"role": "user", "content": "hi"}])


def test_chat_bad_response_shape_is_a_clean_error(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    agent = ns()
    with patch.object(urllib.request, "urlopen",
                      return_value=FakeResponse(json.dumps({"nope": 1}))):
        with pytest.raises(Exception, match="unexpected response shape"):
            agent["chat"]([{"role": "user", "content": "hi"}])


def test_react_two_step_tool_loop(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    agent = ns()
    seen = []

    def fake_weather(args):
        seen.append(args)
        return "sunny, 24C"

    responses = [{"tool": "get_weather", "args": {"city": "Paris"}},
                 {"answer": "It is sunny in Paris."}]
    with patch.object(urllib.request, "urlopen",
                      side_effect=[model_says(r) for r in responses]):
        result = agent["react"]("What is the weather in Paris?",
                                {"get_weather": fake_weather},
                                8, "gpt-4o-mini", "k", "http://llm.test")
    assert result["done"] is True
    assert result["answer"] == "It is sunny in Paris."
    assert seen == [{"city": "Paris"}]
    assert len(result["steps"]) == 1
    step = result["steps"][0]
    assert step["tool"] == "get_weather"
    assert step["args"] == {"city": "Paris"}
    assert step["observation"] == "sunny, 24C"


def test_react_recovers_from_malformed_json(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    agent = ns()
    responses = [FakeResponse(json.dumps(chat_payload("this is not json at all"))),
                 model_says({"answer": "done"})]
    with patch.object(urllib.request, "urlopen", side_effect=responses):
        result = agent["react"]("Say done.", {}, 8,
                                "gpt-4o-mini", "k", "http://llm.test")
    assert result["done"] is True
    assert result["answer"] == "done"
    assert result["steps"] == []


def test_react_unknown_tool_asks_again(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    agent = ns()
    responses = [{"tool": "nope", "args": {}},
                 {"answer": "gave up"}]
    with patch.object(urllib.request, "urlopen",
                      side_effect=[model_says(r) for r in responses]):
        result = agent["react"]("Do it.", {}, 8,
                                "gpt-4o-mini", "k", "http://llm.test")
    assert result["answer"] == "gave up"
    assert result["steps"] == []


def test_react_stops_at_max_steps(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    agent = ns()
    with patch.object(urllib.request, "urlopen",
                      return_value=model_says({"tool": "t", "args": {}})):
        result = agent["react"]("Loop forever.", {"t": lambda a: "x"}, 3,
                                "gpt-4o-mini", "k", "http://llm.test")
    assert result["done"] is False
    assert len(result["steps"]) == 3


def test_react_tool_error_becomes_observation(monkeypatch):
    monkeypatch.setenv("AGK_LLM_API_KEY", "k")
    agent = ns()

    def bad_tool(args):
        raise RuntimeError("kaput")

    responses = [{"tool": "bad", "args": {}},
                 {"answer": "the tool failed"}]
    with patch.object(urllib.request, "urlopen",
                      side_effect=[model_says(r) for r in responses]):
        result = agent["react"]("Try it.", {"bad": bad_tool}, 8,
                                "gpt-4o-mini", "k", "http://llm.test")
    assert result["answer"] == "the tool failed"
    assert result["steps"][0]["observation"] == "the tool raised an error"


def test_react_zero_steps_makes_no_calls(monkeypatch):
    monkeypatch.delenv("AGK_LLM_API_KEY", raising=False)
    agent = ns()
    with patch.object(urllib.request, "urlopen") as m:
        result = agent["react"]("Say hi.", {}, 0,
                                "gpt-4o-mini", "", "http://llm.test")
    m.assert_not_called()
    assert result == {"answer": "", "steps": [], "done": False, "goal": "Say hi."}
