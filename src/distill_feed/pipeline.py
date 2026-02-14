from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

import httpx

from distill_feed.cache import FileCache
from distill_feed.config import Config
from distill_feed.extraction.extractor import extract_content
from distill_feed.extraction.fetcher import fetch_article
from distill_feed.ingestion.feed_parser import parse_feeds
from distill_feed.ingestion.selector import select_items
from distill_feed.ingestion.url_normalize import deduplicate, normalize_url
from distill_feed.models import (
    ExtractionResult,
    FeedItem,
    ItemResult,
    ItemStatus,
    RunReport,
    SourceType,
)
from distill_feed.output.markdown import render_digest, write_digest
from distill_feed.output.report import build_report
from distill_feed.summarization.llm_client import LLMClient
from distill_feed.summarization.prompts import PROMPT_VERSION
from distill_feed.summarization.schemas import SummaryParseError, parse_summary


def _to_item_result(item: FeedItem) -> ItemResult:
    return ItemResult(
        status=ItemStatus.SELECTED,
        url=item.url,
        title=item.title,
        feed_title=item.feed_title,
        date=item.sort_date,
    )


async def run(config: Config) -> RunReport:
    run_id = str(uuid.uuid4())
    timestamp = datetime.now(tz=timezone.utc)
    cache = FileCache(config.cache_dir, max_html_bytes=config.cache_max_html_bytes)

    feed_items = await parse_feeds(config.feeds, timeout=config.timeout)
    direct_items = [
        FeedItem(
            url=url,
            normalized_url=normalize_url(url),
            source_type=SourceType.DIRECT,
        )
        for url in config.urls
    ]

    all_candidates = deduplicate(feed_items + direct_items)
    selected_items, skipped_items = select_items(all_candidates, config.since, config.max_items)

    item_records: list[ItemResult] = []
    for skipped in skipped_items:
        item_records.append(
            ItemResult(
                status=ItemStatus.SKIPPED,
                url=skipped.url,
                title=skipped.title,
                feed_title=skipped.feed_title,
                date=skipped.date,
                skip_reason=skipped.reason,
            )
        )

    if config.dry_run:
        item_records.extend(_to_item_result(item) for item in selected_items)
        report = build_report(
            item_records=item_records,
            config=config,
            run_id=run_id,
            timestamp=timestamp,
            api_used=None,
        )
        digest = render_digest(item_records, config, report)
        write_digest(digest, config.out, timestamp.date())
        return report

    llm_client = LLMClient(config) if config.api_key_value() else None
    semaphore = asyncio.Semaphore(config.concurrency)

    async with httpx.AsyncClient(timeout=config.timeout, follow_redirects=True) as client:

        async def process_one(item: FeedItem) -> ItemResult:
            async with semaphore:
                timings: dict[str, float] = {}
                result = ItemResult(
                    status=ItemStatus.FAILED,
                    url=item.url,
                    title=item.title,
                    feed_title=item.feed_title,
                    date=item.sort_date,
                )

                fetch_started = time.perf_counter()
                fetch = await fetch_article(item.url, client, config, cache)
                timings["fetch_ms"] = (time.perf_counter() - fetch_started) * 1000
                result.fetch = fetch
                if fetch.error or not fetch.html:
                    result.error = fetch.error or "fetch_failed"
                    result.timings = timings
                    return result

                extraction_started = time.perf_counter()
                cached_text = await asyncio.to_thread(cache.get, "text", item.url)
                if cached_text:
                    extraction = ExtractionResult(
                        url=item.url,
                        title=item.title,
                        content=cached_text,
                        content_length=len(cached_text),
                        quality_score=len(cached_text) / max(len(fetch.html), 1),
                        from_cache=True,
                    )
                else:
                    extraction = extract_content(item.url, fetch.html, fallback_title=item.title)
                    if not extraction.error and extraction.content:
                        await asyncio.to_thread(cache.put, "text", item.url, extraction.content)
                timings["extract_ms"] = (time.perf_counter() - extraction_started) * 1000
                result.extraction = extraction
                if extraction.error or not extraction.content:
                    result.error = extraction.error or "extract_failed"
                    result.timings = timings
                    return result

                if llm_client is None:
                    result.error = "missing_api_key"
                    result.timings = timings
                    return result

                summarize_started = time.perf_counter()
                summary_discriminator = PROMPT_VERSION
                cached_summary = await asyncio.to_thread(
                    cache.get, "summary", item.url, summary_discriminator
                )
                if cached_summary:
                    try:
                        summary = parse_summary(cached_summary)
                        usage = None
                    except SummaryParseError:
                        summary = None
                        usage = None
                else:
                    summary = None
                    usage = None

                if summary is None:
                    try:
                        summary, usage = await llm_client.summarize(
                            text=extraction.content,
                            metadata={
                                "title": extraction.title or item.title,
                                "url": item.url,
                                "feed_title": item.feed_title,
                                "published": item.sort_date.isoformat() if item.sort_date else None,
                            },
                            config=config,
                        )
                        await asyncio.to_thread(
                            cache.put,
                            "summary",
                            item.url,
                            summary.model_dump_json(),
                            summary_discriminator,
                        )
                    except Exception as exc:  # noqa: BLE001
                        result.error = str(exc)
                        timings["summarize_ms"] = (time.perf_counter() - summarize_started) * 1000
                        result.timings = timings
                        return result

                timings["summarize_ms"] = (time.perf_counter() - summarize_started) * 1000
                result.status = ItemStatus.SUMMARIZED
                result.summary = summary
                result.token_usage = usage
                result.title = summary.title
                result.timings = timings
                return result

        processed = await asyncio.gather(*(process_one(item) for item in selected_items))
        item_records.extend(processed)

    report = build_report(
        item_records=item_records,
        config=config,
        run_id=run_id,
        timestamp=timestamp,
        api_used=llm_client.api_used if llm_client else None,
    )
    digest = render_digest(item_records, config, report)
    write_digest(digest, config.out, timestamp.date())
    return report
