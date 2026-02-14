from __future__ import annotations

import re
import time

from distill_feed.models import ExtractionResult


TAG_RE = re.compile(r"<[^>]+>")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _fallback_extract(html: str) -> tuple[str, str | None]:
    title_match = TITLE_RE.search(html)
    title = title_match.group(1).strip() if title_match else None
    text = TAG_RE.sub(" ", html)
    cleaned = " ".join(text.split())
    return cleaned, title


def extract_content(url: str, html: str, fallback_title: str | None = None) -> ExtractionResult:
    started = time.perf_counter()
    try:
        try:
            import trafilatura  # type: ignore

            extracted_text = trafilatura.extract(
                html,
                output_format="txt",
                include_comments=False,
                include_tables=False,
                favor_precision=True,
                deduplicate=True,
            )
            metadata = trafilatura.extract_metadata(html)
            title = metadata.title if metadata is not None else None
        except Exception:  # noqa: BLE001
            extracted_text, title = _fallback_extract(html)

        if not extracted_text:
            return ExtractionResult(
                url=url,
                title=fallback_title,
                error="empty_extraction",
                duration_ms=(time.perf_counter() - started) * 1000,
            )

        if not title:
            title = fallback_title

        quality_score = len(extracted_text) / max(len(html), 1)
        return ExtractionResult(
            url=url,
            title=title,
            content=extracted_text,
            content_length=len(extracted_text),
            quality_score=quality_score,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(
            url=url,
            title=fallback_title,
            error=f"extract_error:{exc}",
            duration_ms=(time.perf_counter() - started) * 1000,
        )
