from __future__ import annotations

from distill_feed.ingestion.url_normalize import deduplicate, normalize_url
from distill_feed.models import FeedItem, SourceType


def test_normalize_url_removes_tracking_and_fragment() -> None:
    url = "HTTPS://Example.COM/path/?utm_source=x&b=2&a=1#frag"
    normalized = normalize_url(url)
    assert normalized == "https://example.com/path?a=1&b=2"


def test_normalize_url_trailing_slash_rules() -> None:
    assert normalize_url("https://example.com/path/") == "https://example.com/path"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_deduplicate_prefers_feed_over_direct() -> None:
    direct = FeedItem(
        url="https://example.com/post?utm_source=x",
        normalized_url="",
        source_type=SourceType.DIRECT,
    )
    feed = FeedItem(
        url="https://example.com/post",
        normalized_url="",
        source_type=SourceType.FEED,
    )
    deduped = deduplicate([direct, feed])
    assert len(deduped) == 1
    assert deduped[0].source_type == SourceType.FEED
