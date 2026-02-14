from __future__ import annotations

import asyncio
import time

import httpx

from distill_feed import __version__
from distill_feed.cache import FileCache
from distill_feed.config import Config
from distill_feed.models import FetchResult


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


async def fetch_article(
    url: str,
    client: httpx.AsyncClient,
    config: Config,
    cache: FileCache,
) -> FetchResult:
    started = time.perf_counter()

    cached_html = await asyncio.to_thread(cache.get, "html", url)
    if cached_html:
        return FetchResult(
            url=url,
            status_code=200,
            html=cached_html,
            duration_ms=(time.perf_counter() - started) * 1000,
            from_cache=True,
        )

    headers = {"User-Agent": f"distill-feed/{__version__}"}
    last_error: str | None = None
    status_code: int | None = None

    for attempt in range(1, config.retries + 1):
        try:
            response = await client.get(url, headers=headers, timeout=config.timeout)
            status_code = response.status_code

            if _is_retryable_status(response.status_code) and attempt < config.retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                continue

            if response.status_code >= 400:
                last_error = f"http_error:{response.status_code}"
                break

            html = response.text
            await asyncio.to_thread(cache.put, "html", url, html)
            return FetchResult(
                url=url,
                status_code=response.status_code,
                html=html,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_error = str(exc)
            if attempt < config.retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            break

    return FetchResult(
        url=url,
        status_code=status_code,
        error=last_error or "fetch_failed",
        duration_ms=(time.perf_counter() - started) * 1000,
    )
