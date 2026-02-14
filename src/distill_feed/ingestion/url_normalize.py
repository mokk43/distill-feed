from __future__ import annotations

from collections import OrderedDict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from distill_feed.models import FeedItem, SourceType

TRACKING_KEYS = {
    "ref",
    "source",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    split = urlsplit(url.strip())
    scheme = split.scheme.lower() or "https"
    netloc = split.netloc.lower()
    path = split.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    filtered: list[tuple[str, str]] = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        key_lower = key.lower()
        if key_lower.startswith("utm_") or key_lower in TRACKING_KEYS:
            continue
        filtered.append((key, value))
    filtered.sort(key=lambda x: (x[0], x[1]))

    query = urlencode(filtered)
    return urlunsplit((scheme, netloc, path, query, ""))


def deduplicate(items: list[FeedItem]) -> list[FeedItem]:
    deduped: "OrderedDict[str, FeedItem]" = OrderedDict()
    for item in items:
        normalized = normalize_url(item.url)
        current = item.model_copy(update={"normalized_url": normalized})
        if normalized not in deduped:
            deduped[normalized] = current
            continue

        existing = deduped[normalized]
        if existing.source_type == SourceType.DIRECT and current.source_type == SourceType.FEED:
            deduped[normalized] = current
    return list(deduped.values())
