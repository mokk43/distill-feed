from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI

from distill_feed.config import Config
from distill_feed.models import ArticleSummary, LLMApiUsed, TokenUsage
from distill_feed.summarization.prompts import build_prompt
from distill_feed.summarization.schemas import SummaryParseError, parse_summary


class LLMClient:
    def __init__(self, config: Config) -> None:
        self.client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key_value(),
            timeout=config.timeout,
        )
        self._is_gemini_native = self._is_gemini_native_base_url(config.base_url)
        self.api_used: LLMApiUsed | None = None

    @staticmethod
    def _is_gemini_native_base_url(base_url: str) -> bool:
        parsed = urlparse(base_url.lower())
        host = parsed.netloc or ""
        if "generativelanguage.googleapis.com" not in host:
            return False
        path_segments = [segment for segment in parsed.path.split("/") if segment]
        return "openai" not in path_segments

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code < 600

    @staticmethod
    def _usage_from_response(response: Any) -> TokenUsage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return TokenUsage()

        prompt_tokens = getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0
        completion_tokens = (
            getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0
        )
        total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _responses_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text

        output = getattr(response, "output", None) or []
        parts: list[str] = []
        for item in output:
            content = getattr(item, "content", None) or []
            for part in content:
                text = getattr(part, "text", None)
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _chat_text(response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        if message is None:
            return ""
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for chunk in content:
                text = getattr(chunk, "text", None)
                if text:
                    chunks.append(text)
            return "\n".join(chunks).strip()
        return str(content)

    @staticmethod
    def _should_fallback(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code in (404, 405):
            return True

        message = str(exc).lower()
        return "not supported" in message or "unsupported" in message

    async def _call_responses(self, prompt: str, config: Config) -> tuple[str, TokenUsage]:
        response = await self.client.responses.create(
            model=config.model,
            input=prompt,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            text={"format": {"type": "json_object"}},
        )
        self.api_used = LLMApiUsed.RESPONSES
        return self._responses_text(response), self._usage_from_response(response)

    async def _call_chat(self, prompt: str, config: Config) -> tuple[str, TokenUsage]:
        response = await self.client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=config.temperature,
            max_tokens=config.max_output_tokens,
            response_format={"type": "json_object"},
        )
        self.api_used = LLMApiUsed.CHAT_COMPLETIONS
        return self._chat_text(response), self._usage_from_response(response)

    async def _call_gemini_generate_content(
        self,
        prompt: str,
        config: Config,
    ) -> tuple[str, TokenUsage]:
        api_key = config.api_key_value()
        if not api_key:
            raise RuntimeError("missing_api_key")

        model_path = config.model if config.model.startswith("models/") else f"models/{config.model}"
        endpoint = f"{config.base_url}/{model_path}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

        last_error: Exception | None = None
        for attempt in range(1, config.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=config.timeout) as client:
                    response = await client.post(
                        endpoint,
                        params={"key": api_key},
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                if self._is_retryable_status(response.status_code) and attempt < config.retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue

                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code and self._is_retryable_status(status_code) and attempt < config.retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise RuntimeError(f"gemini_http_error:{status_code}") from exc
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                last_error = exc
                if attempt < config.retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise RuntimeError(f"gemini_request_error:{exc}") from exc
            except ValueError as exc:
                raise RuntimeError(f"gemini_invalid_json:{exc}") from exc
        else:
            raise RuntimeError(f"gemini_request_error:{last_error}")

        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("gemini_no_candidates")

        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        raw_text = "\n".join(part for part in text_parts if part).strip()
        if not raw_text:
            raise RuntimeError("gemini_empty_text")

        usage_meta = data.get("usageMetadata") or {}
        usage = TokenUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", 0) or 0,
            completion_tokens=usage_meta.get("candidatesTokenCount", 0) or 0,
            total_tokens=usage_meta.get("totalTokenCount", 0) or 0,
        )

        # Keep report contract stable (`responses|chat_completions`) for downstream consumers.
        self.api_used = LLMApiUsed.CHAT_COMPLETIONS
        return raw_text, usage

    async def _call_with_fallback(self, prompt: str, config: Config) -> tuple[str, TokenUsage]:
        if self._is_gemini_native:
            return await self._call_gemini_generate_content(prompt, config)

        if self.api_used == LLMApiUsed.CHAT_COMPLETIONS:
            return await self._call_chat(prompt, config)
        if self.api_used == LLMApiUsed.RESPONSES:
            return await self._call_responses(prompt, config)

        try:
            return await self._call_responses(prompt, config)
        except Exception as exc:  # noqa: BLE001
            if not self._should_fallback(exc):
                raise
            return await self._call_chat(prompt, config)

    async def summarize(
        self,
        text: str,
        metadata: dict[str, str | None],
        config: Config,
    ) -> tuple[ArticleSummary, TokenUsage]:
        prompt = build_prompt(
            metadata=metadata,
            text=text,
            preset=config.prompt_preset,
            max_input_chars=config.max_input_chars,
        )

        raw_text, usage = await self._call_with_fallback(prompt, config)
        try:
            summary = parse_summary(raw_text)
            return summary, usage
        except SummaryParseError:
            repair_prompt = (
                "The following output is invalid JSON for the required schema. "
                "Fix it and return only valid JSON.\n\n"
                f"{raw_text}"
            )
            repaired_text, _ = await self._call_with_fallback(repair_prompt, config)
            try:
                summary = parse_summary(repaired_text)
                return summary, usage
            except SummaryParseError as exc:
                raise SummaryParseError(f"json_parse_error_after_repair:{exc}") from exc
