from __future__ import annotations

import json
import sys
from datetime import date, datetime

from distill_feed.config import Config
from distill_feed.models import ItemResult, ItemStatus, LLMApiUsed, RunInputs, RunLLM, RunReport, RunSelection
from distill_feed.summarization.prompts import PROMPT_VERSION


def build_report(
    item_records: list[ItemResult],
    config: Config,
    run_id: str,
    timestamp: datetime,
    api_used: LLMApiUsed | None,
) -> RunReport:
    success_count = sum(1 for item in item_records if item.status == ItemStatus.SUMMARIZED)
    failure_count = sum(1 for item in item_records if item.status == ItemStatus.FAILED)
    skip_count = sum(1 for item in item_records if item.status == ItemStatus.SKIPPED)

    since_value: datetime | date | None = None
    if config.since:
        try:
            if "T" in config.since:
                since_value = datetime.fromisoformat(config.since.replace("Z", "+00:00"))
            else:
                since_value = date.fromisoformat(config.since)
        except ValueError:
            since_value = None

    return RunReport(
        run_id=run_id,
        timestamp=timestamp,
        inputs=RunInputs(
            feed_count=len(config.feeds),
            url_count=len(config.urls),
            feeds=config.feeds,
            urls=config.urls,
        ),
        selection=RunSelection(
            total_selected=sum(1 for item in item_records if item.status != ItemStatus.SKIPPED),
            since=since_value,
            max_items=config.max_items,
        ),
        llm=RunLLM(
            base_url=config.base_url,
            model=config.model,
            api_used=api_used,
            prompt_version=PROMPT_VERSION,
        ),
        items=item_records,
        success_count=success_count,
        failure_count=failure_count,
        skip_count=skip_count,
    )


def emit_report(report: RunReport) -> None:
    payload = report.model_dump(mode="json")
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
