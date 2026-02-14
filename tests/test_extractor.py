from __future__ import annotations

from distill_feed.extraction.extractor import extract_content


def test_extract_content_returns_text(fixtures_dir) -> None:
    html = (fixtures_dir / "sample_article.html").read_text(encoding="utf-8")
    result = extract_content("https://example.com/post", html, fallback_title="Fallback")
    assert result.error is None
    assert result.content_length > 10
    assert result.quality_score > 0
