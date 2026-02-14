from __future__ import annotations

import pytest

from distill_feed.summarization.schemas import SummaryParseError, parse_summary


def test_parse_summary_valid(fixtures_dir) -> None:
    raw = (fixtures_dir / "llm_response_valid.json").read_text(encoding="utf-8")
    parsed = parse_summary(raw)
    assert parsed.title == "Example Article"
    assert parsed.confidence == 0.87


def test_parse_summary_invalid_raises(fixtures_dir) -> None:
    raw = (fixtures_dir / "llm_response_invalid.json").read_text(encoding="utf-8")
    with pytest.raises(SummaryParseError):
        parse_summary(raw)
