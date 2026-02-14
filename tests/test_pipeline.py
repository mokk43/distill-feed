from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from distill_feed.config import Config
from distill_feed.models import FeedItem, FetchResult, ItemStatus, SourceType
from distill_feed.pipeline import run


def test_pipeline_dry_run_skips_llm_and_marks_selected(tmp_path, monkeypatch) -> None:
    async def fake_parse_feeds(feed_urls, timeout):  # noqa: ANN001, ANN202
        return [
            FeedItem(
                url="https://example.com/a",
                normalized_url="https://example.com/a",
                title="A",
                published=datetime(2026, 2, 14, tzinfo=timezone.utc),
                source_type=SourceType.FEED,
            )
        ]

    monkeypatch.setattr("distill_feed.pipeline.parse_feeds", fake_parse_feeds)
    config = Config(
        feeds=["https://feeds"],
        urls=[],
        dry_run=True,
        out=tmp_path / "digest.md",
        cache_dir=tmp_path / "cache",
    )
    report = asyncio.run(run(config))

    assert any(item.status == ItemStatus.SELECTED for item in report.items)
    assert report.success_count == 0
    outputs = list(tmp_path.glob("digest-*.md"))
    assert len(outputs) == 1


def test_pipeline_missing_api_key_marks_failed(tmp_path, monkeypatch) -> None:
    async def fake_parse_feeds(feed_urls, timeout):  # noqa: ANN001, ANN202
        return []

    async def fake_fetch_article(url, client, config, cache):  # noqa: ANN001, ANN202
        return FetchResult(url=url, status_code=200, html="<html><body>content</body></html>")

    def fake_extract_content(url, html, fallback_title=None):  # noqa: ANN001, ANN202
        from distill_feed.models import ExtractionResult

        return ExtractionResult(
            url=url,
            title="Title",
            content="Body text",
            content_length=9,
            quality_score=0.1,
        )

    monkeypatch.setattr("distill_feed.pipeline.parse_feeds", fake_parse_feeds)
    monkeypatch.setattr("distill_feed.pipeline.fetch_article", fake_fetch_article)
    monkeypatch.setattr("distill_feed.pipeline.extract_content", fake_extract_content)

    config = Config(
        feeds=[],
        urls=["https://example.com/direct"],
        out=tmp_path / "digest.md",
        dry_run=False,
        cache_dir=tmp_path / "cache",
    )
    report = asyncio.run(run(config))

    assert any(item.status == ItemStatus.FAILED for item in report.items)
    assert any(item.error == "missing_api_key" for item in report.items)
