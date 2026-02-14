from __future__ import annotations

from datetime import datetime, timezone

from distill_feed.config import Config
from distill_feed.models import ItemResult, ItemStatus, LLMApiUsed
from distill_feed.output.report import build_report


def test_build_report_counts_statuses() -> None:
    config = Config(feeds=["f"], urls=["u"], max_items=10)
    items = [
        ItemResult(status=ItemStatus.SUMMARIZED, url="https://a"),
        ItemResult(status=ItemStatus.FAILED, url="https://b"),
        ItemResult(status=ItemStatus.SKIPPED, url="https://c", skip_reason="reason"),
    ]

    report = build_report(
        item_records=items,
        config=config,
        run_id="id",
        timestamp=datetime(2026, 2, 14, tzinfo=timezone.utc),
        api_used=LLMApiUsed.RESPONSES,
    )

    assert report.success_count == 1
    assert report.failure_count == 1
    assert report.skip_count == 1
    assert report.llm.api_used == LLMApiUsed.RESPONSES
