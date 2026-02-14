from __future__ import annotations

import hashlib
from pathlib import Path


class FileCache:
    def __init__(self, cache_dir: Path, max_html_bytes: int = 5 * 1024 * 1024) -> None:
        self.cache_dir = cache_dir.expanduser()
        self.max_html_bytes = max_html_bytes
        for namespace in ("html", "text", "summary", "meta"):
            (self.cache_dir / namespace).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def cache_key(url: str, discriminator: str = "") -> str:
        raw = f"{url}{discriminator}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _path_for(self, namespace: str, url: str, discriminator: str = "") -> Path:
        key = self.cache_key(url, discriminator)
        ext = {
            "html": ".html",
            "text": ".txt",
            "summary": ".json",
            "meta": ".json",
        }.get(namespace, ".txt")
        return self.cache_dir / namespace / f"{key}{ext}"

    def get(self, namespace: str, url: str, discriminator: str = "") -> str | None:
        path = self._path_for(namespace, url, discriminator)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def put(
        self,
        namespace: str,
        url: str,
        data: str,
        discriminator: str = "",
    ) -> None:
        if namespace == "html" and len(data.encode("utf-8", errors="ignore")) > self.max_html_bytes:
            return
        path = self._path_for(namespace, url, discriminator)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
        except OSError:
            return
