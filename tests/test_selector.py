from __future__ import annotations

from datetime import datetime, timezone

from distill_feed.ingestion.selector import select_items
from distill_feed.models import FeedItem, SourceType


def _item(url: str, published: datetime | None) -> FeedItem:
    return FeedItem(
        url=url,
        normalized_url=url,
        title=url,
        published=published,
        source_type=SourceType.FEED,
    )


def test_since_excludes_only_dated_older_items() -> None:
    newer = _item("https://a", datetime(2026, 2, 14, tzinfo=timezone.utc))
    older = _item("https://b", datetime(2026, 2, 10, tzinfo=timezone.utc))
    undated = _item("https://c", None)

    selected, skipped = select_items([older, undated, newer], "2026-02-12", None)
    assert [item.url for item in selected] == ["https://a", "https://c"]
    assert len(skipped) == 1
    assert skipped[0].reason == "older_than_since"


def test_max_items_is_global_cap() -> None:
    first = _item("https://1", datetime(2026, 2, 14, tzinfo=timezone.utc))
    second = _item("https://2", datetime(2026, 2, 13, tzinfo=timezone.utc))
    third = _item("https://3", datetime(2026, 2, 12, tzinfo=timezone.utc))

    selected, skipped = select_items([third, second, first], None, 2)
    assert [item.url for item in selected] == ["https://1", "https://2"]
    assert len(skipped) == 1
    assert skipped[0].url == "https://3"
    assert skipped[0].reason == "max_items_limit"
