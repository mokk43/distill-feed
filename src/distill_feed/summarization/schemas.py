from __future__ import annotations

import json
import re

from pydantic import ValidationError

from distill_feed.models import ArticleSummary


class SummaryParseError(Exception):
    """Raised when a summary cannot be parsed into the contract schema."""


JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json_blob(raw: str) -> str:
    stripped = raw.strip()
    fence_match = JSON_FENCE_RE.search(stripped)
    if fence_match:
        return fence_match.group(1).strip()

    first = stripped.find("{")
    last = stripped.rfind("}")
    if first != -1 and last != -1 and first < last:
        return stripped[first : last + 1]
    return stripped


def parse_summary(raw: str) -> ArticleSummary:
    blob = _extract_json_blob(raw)
    try:
        payload = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise SummaryParseError(f"json_decode_error:{exc}") from exc

    try:
        return ArticleSummary.model_validate(payload)
    except ValidationError as exc:
        raise SummaryParseError(f"schema_validation_error:{exc}") from exc
