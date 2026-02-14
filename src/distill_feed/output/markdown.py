from __future__ import annotations

from datetime import date
from pathlib import Path

from distill_feed.config import Config
from distill_feed.models import ItemResult, ItemStatus, RunReport
from distill_feed.summarization.prompts import PROMPT_VERSION


def _render_bullets(values: list[str]) -> list[str]:
    if not values:
        return ["- (none)"]
    return [f"- {value}" for value in values]


def render_digest(items: list[ItemResult], config: Config, report: RunReport) -> str:
    lines: list[str] = []
    lines.append("# Distill Feed Digest")
    lines.append("")
    lines.append(f"- Run timestamp: {report.timestamp.isoformat()}")
    lines.append(f"- Inputs: feeds={report.inputs.feed_count}, urls={report.inputs.url_count}")
    lines.append(f"- Items selected: {report.selection.total_selected}")
    lines.append(
        "- LLM: "
        f"base_url={report.llm.base_url}, "
        f"model={report.llm.model}, "
        f"llm_api_used={report.llm.api_used.value if report.llm.api_used else 'none'}, "
        f"prompt_version={PROMPT_VERSION}"
    )
    lines.append(f"- Success: {report.success_count}")
    lines.append(f"- Failed: {report.failure_count}")
    lines.append("")

    processed = [item for item in items if item.status != ItemStatus.SKIPPED]
    for item in processed:
        lines.append(f"## {item.summary.title if item.summary else (item.title or 'Untitled')}")
        lines.append(f"- Source: {item.url}")
        lines.append(f"- Feed: {item.feed_title or 'direct'}")
        lines.append(f"- Published: {item.date.isoformat() if item.date else 'unknown'}")
        if item.extraction:
            lines.append(
                "- Extraction: "
                f"quality={item.extraction.quality_score:.4f}, "
                f"chars={item.extraction.content_length}"
            )
        else:
            lines.append("- Extraction: unavailable")

        if item.summary:
            lines.append(f"- One sentence: {item.summary.one_sentence}")
            lines.append("- Summary:")
            lines.extend(_render_bullets(item.summary.summary_bullets))
            lines.append("- Key takeaways:")
            lines.extend(_render_bullets(item.summary.key_takeaways))
            lines.append("- Why it matters:")
            lines.extend(_render_bullets(item.summary.why_it_matters))
            if item.summary.notable_quotes:
                lines.append("- Quotes:")
                for quote in item.summary.notable_quotes:
                    lines.append(f'- "{quote.quote}" -- {quote.context}')
            if item.summary.tags:
                lines.append(f"- Tags: {', '.join(item.summary.tags)}")
            lines.append(f"- Confidence: {item.summary.confidence}")
        elif item.status == ItemStatus.SELECTED and config.dry_run:
            lines.append("- One sentence: (dry-run; summarization skipped)")
            lines.append("- Summary:")
            lines.append("- (dry-run)")
            lines.append("- Key takeaways:")
            lines.append("- (dry-run)")
            lines.append("- Why it matters:")
            lines.append("- (dry-run)")
        else:
            lines.append(f"- Error: {item.error or 'unknown_error'}")
        lines.append("")

    skipped = [item for item in items if item.status == ItemStatus.SKIPPED]
    failed = [item for item in items if item.status == ItemStatus.FAILED]

    lines.append("## Skipped Items")
    if not skipped:
        lines.append("- None")
    else:
        for item in skipped:
            lines.append(f"- {item.url} -- {item.skip_reason or 'unspecified'}")
    lines.append("")

    lines.append("## Failed Items")
    if not failed:
        lines.append("- None")
    else:
        for item in failed:
            lines.append(f"- {item.url} -- {item.error or 'unknown_error'}")
    lines.append("")

    return "\n".join(lines)


def write_digest(content: str, out_base: Path, run_date: date) -> Path:
    stem = out_base.stem
    suffix = out_base.suffix
    target = out_base.with_name(f"{stem}-{run_date.strftime('%Y%m%d')}{suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
