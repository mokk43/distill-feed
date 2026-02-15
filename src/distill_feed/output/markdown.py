from __future__ import annotations

from datetime import date
from pathlib import Path

from distill_feed.config import Config
from distill_feed.models import ItemResult, ItemStatus, RunReport


def _render_paragraph(values: list[str]) -> str:
    text = " ".join(value.strip() for value in values if value.strip())
    return text or "(none)"


def render_digest(items: list[ItemResult], config: Config, report: RunReport) -> str:
    _ = (config, report)  # keep signature stable while rendering article-only output
    lines: list[str] = []

    processed = [item for item in items if item.status == ItemStatus.SUMMARIZED]
    for item in processed:
        summary = item.summary
        if summary is None:
            continue

        lines.append(f"## {summary.title or item.title or 'Untitled'}")
        lines.append(f"* Source: {item.url}")
        lines.append(f"* Published: {item.date.strftime('%Y-%m-%d') if item.date else 'unknown'}")
        lines.append("")
        lines.append(summary.one_sentence.strip() or "(none)")
        lines.append("")
        lines.append("#### Summary")
        lines.append(_render_paragraph(summary.summary_bullets))
        lines.append("")
        lines.append("#### Key takeaways")
        lines.append(_render_paragraph(summary.key_takeaways))
        lines.append("")
        lines.append("#### Why it matters")
        lines.append(_render_paragraph(summary.why_it_matters))
        if summary.notable_quotes:
            lines.append("")
            lines.append("#### Notable quotes")
            for quote in summary.notable_quotes:
                quote_text = quote.quote.strip()
                context_text = quote.context.strip()
                if context_text:
                    lines.append(f'"{quote_text}" -- {context_text}')
                else:
                    lines.append(f'"{quote_text}"')
        lines.append("")

    return "\n".join(lines)


def write_digest(content: str, out_base: Path, run_date: date) -> Path:
    stem = out_base.stem
    suffix = out_base.suffix
    target = out_base.with_name(f"{stem}-{run_date.strftime('%Y%m%d')}{suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
