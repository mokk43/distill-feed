from __future__ import annotations

from datetime import date, datetime, time, timezone

from distill_feed.models import FeedItem, SkippedItem


def parse_since_value(raw: str | None) -> datetime | None:
    if not raw:
        return None

    candidate = raw.strip()
    try:
        if "T" in candidate:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed

        parsed_date = date.fromisoformat(candidate)
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"invalid --since value: {raw}") from exc


def _sort_key(item: FeedItem) -> tuple[int, float, str]:
    if item.sort_date is None:
        return (1, 0.0, item.normalized_url)
    dt = item.sort_date
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (0, -dt.timestamp(), item.normalized_url)


def select_items(
    items: list[FeedItem],
    since: datetime | str | None,
    max_items: int | None,
) -> tuple[list[FeedItem], list[SkippedItem]]:
    if isinstance(since, str):
        since_dt = parse_since_value(since)
    else:
        since_dt = since

    sorted_items = sorted(items, key=_sort_key)
    filtered: list[FeedItem] = []
    skipped: list[SkippedItem] = []

    for item in sorted_items:
        item_date = item.sort_date
        if since_dt and item_date:
            dated = item_date if item_date.tzinfo else item_date.replace(tzinfo=timezone.utc)
            if dated < since_dt:
                skipped.append(
                    SkippedItem(
                        url=item.url,
                        normalized_url=item.normalized_url,
                        title=item.title,
                        feed_title=item.feed_title,
                        date=item.sort_date,
                        reason="older_than_since",
                    )
                )
                continue
        filtered.append(item)

    if max_items is None:
        return filtered, skipped

    selected = filtered[:max_items]
    for item in filtered[max_items:]:
        skipped.append(
            SkippedItem(
                url=item.url,
                normalized_url=item.normalized_url,
                title=item.title,
                feed_title=item.feed_title,
                date=item.sort_date,
                reason="max_items_limit",
            )
        )
    return selected, skipped
