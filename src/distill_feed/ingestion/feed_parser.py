from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from xml.etree import ElementTree as ET

import httpx

from distill_feed.ingestion.url_normalize import normalize_url
from distill_feed.models import FeedItem, SourceType

logger = logging.getLogger(__name__)


def _to_datetime(value: struct_time | None) -> datetime | None:
    if value is None:
        return None
    return datetime(
        value.tm_year,
        value.tm_mon,
        value.tm_mday,
        value.tm_hour,
        value.tm_min,
        value.tm_sec,
        tzinfo=timezone.utc,
    )


async def _parse_single_feed(
    client: httpx.AsyncClient,
    feed_url: str,
) -> list[FeedItem]:
    try:
        response = await client.get(feed_url)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("feed fetch failed for %s: %s", feed_url, exc)
        return []

    try:
        import feedparser  # type: ignore

        parsed = feedparser.parse(response.text)
        feed_title = getattr(parsed.feed, "title", None)

        items: list[FeedItem] = []
        for entry in parsed.entries:
            link = getattr(entry, "link", None)
            if not link:
                continue

            items.append(
                FeedItem(
                    url=link,
                    normalized_url=normalize_url(link),
                    title=getattr(entry, "title", None),
                    feed_title=feed_title,
                    published=_to_datetime(getattr(entry, "published_parsed", None)),
                    updated=_to_datetime(getattr(entry, "updated_parsed", None)),
                    author=getattr(entry, "author", None),
                    source_type=SourceType.FEED,
                )
            )
        return items
    except Exception:  # noqa: BLE001
        return _parse_feed_without_feedparser(response.text)


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_feed_without_feedparser(raw_xml: str) -> list[FeedItem]:
    items: list[FeedItem] = []
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return []

    if root.tag.endswith("rss") or root.find("channel") is not None:
        channel = root.find("channel")
        feed_title = channel.findtext("title") if channel is not None else None
        entries = channel.findall("item") if channel is not None else []
        for entry in entries:
            link = entry.findtext("link")
            if not link:
                continue
            published_raw = entry.findtext("pubDate")
            published = _to_utc(parsedate_to_datetime(published_raw)) if published_raw else None
            items.append(
                FeedItem(
                    url=link,
                    normalized_url=normalize_url(link),
                    title=entry.findtext("title"),
                    feed_title=feed_title,
                    published=published,
                    updated=None,
                    author=entry.findtext("author"),
                    source_type=SourceType.FEED,
                )
            )
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    feed_title = root.findtext("atom:title", namespaces=ns)
    for entry in root.findall("atom:entry", ns):
        link_node = entry.find("atom:link", ns)
        link = None
        if link_node is not None:
            link = link_node.attrib.get("href")
        if not link:
            continue
        updated_raw = entry.findtext("atom:updated", namespaces=ns)
        updated = None
        if updated_raw:
            try:
                updated = _to_utc(datetime.fromisoformat(updated_raw.replace("Z", "+00:00")))
            except ValueError:
                updated = None
        items.append(
            FeedItem(
                url=link,
                normalized_url=normalize_url(link),
                title=entry.findtext("atom:title", namespaces=ns),
                feed_title=feed_title,
                published=None,
                updated=updated,
                author=entry.findtext("atom:author/atom:name", namespaces=ns),
                source_type=SourceType.FEED,
            )
        )
    return items


async def parse_feeds(feed_urls: list[str], timeout: float) -> list[FeedItem]:
    if not feed_urls:
        return []

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        results = await asyncio.gather(*(_parse_single_feed(client, url) for url in feed_urls))

    merged: list[FeedItem] = []
    for items in results:
        merged.extend(items)
    return merged
