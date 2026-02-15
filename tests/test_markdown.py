from __future__ import annotations

from datetime import datetime, timezone

from distill_feed.config import Config
from distill_feed.models import (
    ArticleSummary,
    ItemResult,
    ItemStatus,
    RunInputs,
    RunLLM,
    RunReport,
    RunSelection,
)
from distill_feed.output.markdown import render_digest, write_digest


def test_write_digest_adds_date_suffix(tmp_path) -> None:
    target = write_digest("hello", tmp_path / "digest.md", datetime(2026, 2, 14).date())
    assert target.name == "digest-20260214.md"
    assert target.read_text(encoding="utf-8") == "hello"


def test_render_digest_has_required_header_fields() -> None:
    config = Config(feeds=[], urls=[])
    report = RunReport(
        run_id="r1",
        timestamp=datetime(2026, 2, 14, tzinfo=timezone.utc),
        inputs=RunInputs(feed_count=1, url_count=2, feeds=["f"], urls=["u1", "u2"]),
        selection=RunSelection(total_selected=1),
        llm=RunLLM(base_url="https://api.openai.com/v1", model="m", prompt_version="1.0"),
        items=[],
        success_count=1,
        failure_count=0,
        skip_count=0,
    )
    item = ItemResult(
        status=ItemStatus.SUMMARIZED,
        url="https://example.com/post",
        date=datetime(2026, 2, 14, 12, 34, 56, tzinfo=timezone.utc),
        summary=ArticleSummary(
            title="Title",
            one_sentence="One sentence",
            summary_bullets=["A"],
            key_takeaways=["B"],
            why_it_matters=["C"],
            notable_quotes=[],
            tags=["x"],
            confidence=0.8,
        ),
    )
    text = render_digest([item], config, report)
    assert "Run timestamp" not in text
    assert "llm_api_used" not in text
    assert "## Title" in text
    assert "Published: 2026-02-14" in text
    assert "- A" not in text
    assert "Skipped Items" not in text
