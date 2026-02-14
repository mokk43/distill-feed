from __future__ import annotations

import asyncio
import httpx

from distill_feed.ingestion.feed_parser import parse_feeds


def test_parse_feeds_extracts_items(fixtures_dir, monkeypatch) -> None:
    body = (fixtures_dir / "sample_rss.xml").read_text(encoding="utf-8")

    async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN202
        request = httpx.Request("GET", url)
        return httpx.Response(200, text=body, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    items = asyncio.run(parse_feeds(["https://feeds.example/rss"], timeout=10))
    assert len(items) == 3
    assert items[0].feed_title == "Example Feed"
    assert items[0].url == "https://example.com/newest"
