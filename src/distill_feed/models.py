from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    FEED = "feed"
    DIRECT = "direct"


class ItemStatus(str, Enum):
    SELECTED = "selected"
    SUMMARIZED = "summarized"
    SKIPPED = "skipped"
    FAILED = "failed"


class LLMApiUsed(str, Enum):
    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"


class FeedItem(BaseModel):
    """A candidate article discovered from a feed or direct URL."""

    url: str
    normalized_url: str
    title: str | None = None
    feed_title: str | None = None
    published: datetime | None = None
    updated: datetime | None = None
    author: str | None = None
    source_type: SourceType

    @property
    def sort_date(self) -> datetime | None:
        return self.published or self.updated


class SkippedItem(BaseModel):
    url: str
    normalized_url: str
    title: str | None = None
    feed_title: str | None = None
    date: datetime | None = None
    reason: str


class FetchResult(BaseModel):
    """Result of HTTP-fetching an article URL."""

    url: str
    status_code: int | None = None
    html: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    from_cache: bool = False


class ExtractionResult(BaseModel):
    """Result of readability extraction on fetched HTML."""

    url: str
    title: str | None = None
    content: str = ""
    content_length: int = 0
    quality_score: float = 0.0
    error: str | None = None
    duration_ms: float = 0.0
    from_cache: bool = False


class Quote(BaseModel):
    quote: str
    context: str


class ArticleSummary(BaseModel):
    """Structured summary returned by LLM (must match prompt schema)."""

    title: str
    one_sentence: str
    summary_bullets: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    why_it_matters: list[str] = Field(default_factory=list)
    notable_quotes: list[Quote] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ItemResult(BaseModel):
    """Full processing record for a single article."""

    status: ItemStatus
    url: str
    title: str | None = None
    feed_title: str | None = None
    date: datetime | None = None
    skip_reason: str | None = None
    fetch: FetchResult | None = None
    extraction: ExtractionResult | None = None
    summary: ArticleSummary | None = None
    error: str | None = None
    token_usage: TokenUsage | None = None
    timings: dict[str, float] = Field(default_factory=dict)


class RunInputs(BaseModel):
    feed_count: int
    url_count: int
    feeds: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)


class RunSelection(BaseModel):
    total_selected: int
    since: datetime | date | None = None
    max_items: int | None = None


class RunLLM(BaseModel):
    base_url: str
    model: str
    api_used: LLMApiUsed | None = None
    prompt_version: str


class RunReport(BaseModel):
    """Machine-readable run report (--json output)."""

    run_id: str
    timestamp: datetime
    inputs: RunInputs
    selection: RunSelection
    llm: RunLLM
    items: list[ItemResult]
    success_count: int = 0
    failure_count: int = 0
    skip_count: int = 0
