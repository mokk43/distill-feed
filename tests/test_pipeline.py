from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from distill_feed.config import Config
from distill_feed.models import ArticleSummary, ExtractionResult, FeedItem, FetchResult, ItemStatus, SourceType
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
        api_key="",
        cache_dir=tmp_path / "cache",
    )
    report = asyncio.run(run(config))

    assert any(item.status == ItemStatus.FAILED for item in report.items)
    assert any(item.error == "missing_api_key" for item in report.items)


def test_pipeline_fetches_only_selected_max_items(tmp_path, monkeypatch) -> None:
    async def fake_parse_feeds(feed_urls, timeout):  # noqa: ANN001, ANN202
        return [
            FeedItem(
                url="https://example.com/newest",
                normalized_url="https://example.com/newest",
                title="Newest",
                published=datetime(2026, 2, 14, tzinfo=timezone.utc),
                source_type=SourceType.FEED,
            ),
            FeedItem(
                url="https://example.com/middle",
                normalized_url="https://example.com/middle",
                title="Middle",
                published=datetime(2026, 2, 13, tzinfo=timezone.utc),
                source_type=SourceType.FEED,
            ),
            FeedItem(
                url="https://example.com/oldest",
                normalized_url="https://example.com/oldest",
                title="Oldest",
                published=datetime(2026, 2, 12, tzinfo=timezone.utc),
                source_type=SourceType.FEED,
            ),
        ]

    fetch_calls: list[str] = []

    async def fake_fetch_article(url, client, config, cache):  # noqa: ANN001, ANN202
        fetch_calls.append(url)
        return FetchResult(url=url, status_code=200, html="<html><body>content</body></html>")

    def fake_extract_content(url, html, fallback_title=None):  # noqa: ANN001, ANN202
        return ExtractionResult(
            url=url,
            title=fallback_title or "Title",
            content="Body text",
            content_length=9,
            quality_score=0.1,
        )

    class FakeLLMClient:
        def __init__(self, config):  # noqa: ANN001
            self.api_used = None

        async def summarize(self, text, metadata, config):  # noqa: ANN001, ANN202
            return (
                ArticleSummary(
                    title=metadata["title"] or "Title",
                    one_sentence="One sentence",
                    summary_bullets=["Summary sentence."],
                    key_takeaways=["Takeaway sentence."],
                    why_it_matters=["Why sentence."],
                    notable_quotes=[],
                    tags=[],
                    confidence=0.9,
                ),
                None,
            )

    monkeypatch.setattr("distill_feed.pipeline.parse_feeds", fake_parse_feeds)
    monkeypatch.setattr("distill_feed.pipeline.fetch_article", fake_fetch_article)
    monkeypatch.setattr("distill_feed.pipeline.extract_content", fake_extract_content)
    monkeypatch.setattr("distill_feed.pipeline.LLMClient", FakeLLMClient)

    config = Config(
        feeds=["https://feeds"],
        urls=[],
        max_items=1,
        api_key="test-key",
        out=tmp_path / "digest.md",
        dry_run=False,
        cache_dir=tmp_path / "cache",
    )
    asyncio.run(run(config))

    assert fetch_calls == ["https://example.com/newest"]
