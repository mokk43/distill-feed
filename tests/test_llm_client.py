from __future__ import annotations

import asyncio

import httpx

from distill_feed.config import Config
from distill_feed.models import LLMApiUsed
from distill_feed.summarization.llm_client import LLMClient


class _Usage:
    def __init__(self) -> None:
        self.prompt_tokens = 10
        self.completion_tokens = 20
        self.total_tokens = 30


class _Resp:
    def __init__(self, text: str) -> None:
        self.output_text = text
        self.usage = _Usage()


class _ChatMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _ChatMessage(content)


class _ChatResp:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage()


class _FallbackError(Exception):
    status_code = 404


def test_llm_client_falls_back_to_chat() -> None:
    config = Config(feeds=[], urls=[], api_key="k")
    client = LLMClient(config)

    class FakeResponses:
        async def create(self, **kwargs):  # noqa: ANN003
            raise _FallbackError("unsupported")

    class FakeCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            return _ChatResp(
                '{"title":"T","one_sentence":"S","summary_bullets":[],"key_takeaways":[],"why_it_matters":[],"notable_quotes":[],"tags":[],"confidence":0.5}'
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        responses = FakeResponses()
        chat = FakeChat()

    client.client = FakeClient()
    summary, _usage = asyncio.run(client.summarize("text", {"url": "https://x"}, config))
    assert summary.title == "T"
    assert client.api_used == LLMApiUsed.CHAT_COMPLETIONS


def test_llm_client_uses_responses_when_available() -> None:
    config = Config(feeds=[], urls=[], api_key="k")
    client = LLMClient(config)

    class FakeResponses:
        async def create(self, **kwargs):  # noqa: ANN003
            return _Resp(
                '{"title":"T2","one_sentence":"S","summary_bullets":[],"key_takeaways":[],"why_it_matters":[],"notable_quotes":[],"tags":[],"confidence":0.1}'
            )

    class FakeCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            raise AssertionError("chat should not be called")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        responses = FakeResponses()
        chat = FakeChat()

    client.client = FakeClient()
    summary, usage = asyncio.run(client.summarize("text", {"url": "https://x"}, config))
    assert summary.title == "T2"
    assert usage.total_tokens == 30
    assert client.api_used == LLMApiUsed.RESPONSES


def test_llm_client_uses_gemini_generate_content(monkeypatch) -> None:
    config = Config(
        feeds=[],
        urls=[],
        api_key="gk",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-2.0-flash",
    )
    client = LLMClient(config)

    async def fake_post(self, url, **kwargs):  # noqa: ANN001, ANN202
        assert url.endswith("/v1beta/models/gemini-2.0-flash:generateContent")
        assert kwargs["params"]["key"] == "gk"
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"title":"Gemini","one_sentence":"S","summary_bullets":[],'
                                    '"key_takeaways":[],"why_it_matters":[],"notable_quotes":[],'
                                    '"tags":[],"confidence":0.9}'
                                )
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 11,
                "candidatesTokenCount": 7,
                "totalTokenCount": 18,
            },
        }
        request = httpx.Request("POST", url)
        return httpx.Response(200, json=payload, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    summary, usage = asyncio.run(client.summarize("text", {"url": "https://x"}, config))
    assert summary.title == "Gemini"
    assert usage.total_tokens == 18
    assert client.api_used == LLMApiUsed.CHAT_COMPLETIONS


def test_llm_client_does_not_route_openai_compatible_gemini_to_native() -> None:
    config = Config(
        feeds=[],
        urls=[],
        api_key="gk",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        model="gemini-2.0-flash",
    )
    client = LLMClient(config)

    class FakeResponses:
        async def create(self, **kwargs):  # noqa: ANN003
            return _Resp(
                '{"title":"Compat","one_sentence":"S","summary_bullets":[],"key_takeaways":[],"why_it_matters":[],"notable_quotes":[],"tags":[],"confidence":0.3}'
            )

    class FakeCompletions:
        async def create(self, **kwargs):  # noqa: ANN003
            raise AssertionError("chat should not be called")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        responses = FakeResponses()
        chat = FakeChat()

    client.client = FakeClient()
    summary, _usage = asyncio.run(client.summarize("text", {"url": "https://x"}, config))
    assert summary.title == "Compat"
    assert client.api_used == LLMApiUsed.RESPONSES


def test_llm_client_retries_retryable_gemini_status(monkeypatch) -> None:
    config = Config(
        feeds=[],
        urls=[],
        api_key="gk",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-2.0-flash",
        retries=2,
    )
    client = LLMClient(config)
    calls = {"count": 0}

    async def fake_post(self, url, **kwargs):  # noqa: ANN001, ANN202
        calls["count"] += 1
        request = httpx.Request("POST", url)
        if calls["count"] == 1:
            return httpx.Response(429, json={"error": "rate_limited"}, request=request)
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"title":"Retried","one_sentence":"S","summary_bullets":[],'
                                    '"key_takeaways":[],"why_it_matters":[],"notable_quotes":[],'
                                    '"tags":[],"confidence":0.9}'
                                )
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 11,
                "candidatesTokenCount": 7,
                "totalTokenCount": 18,
            },
        }
        return httpx.Response(200, json=payload, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    summary, _usage = asyncio.run(client.summarize("text", {"url": "https://x"}, config))
    assert summary.title == "Retried"
    assert calls["count"] == 2
