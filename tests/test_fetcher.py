from __future__ import annotations

import asyncio
import httpx

from distill_feed.cache import FileCache
from distill_feed.config import Config
from distill_feed.extraction.fetcher import fetch_article


def test_fetch_article_success_and_cache(tmp_path, monkeypatch) -> None:
    async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN202
        request = httpx.Request("GET", url)
        return httpx.Response(200, text="<html>ok</html>", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    config = Config(feeds=[], urls=[], cache_dir=tmp_path, retries=1)
    cache = FileCache(tmp_path)

    async def run_case():  # noqa: ANN202
        async with httpx.AsyncClient() as client:
            first = await fetch_article("https://example.com/post", client, config, cache)
            second = await fetch_article("https://example.com/post", client, config, cache)
            return first, second

    first, second = asyncio.run(run_case())

    assert first.error is None
    assert first.html == "<html>ok</html>"
    assert second.from_cache is True
