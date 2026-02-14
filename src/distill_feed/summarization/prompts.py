from __future__ import annotations

import json

PROMPT_VERSION = "1.0"

DEFAULT_TEMPLATE = """You are a precise technical editor.
Summarize the article into strict JSON that matches this schema exactly:
{schema}

Rules:
- Output must be valid JSON only.
- Keep factual grounding in the provided content.
- If uncertain, lower confidence.
"""

PRESETS: dict[str, str] = {"default": DEFAULT_TEMPLATE}

SUMMARY_SCHEMA = {
    "title": "string",
    "one_sentence": "string",
    "summary_bullets": ["string"],
    "key_takeaways": ["string"],
    "why_it_matters": ["string"],
    "notable_quotes": [{"quote": "string", "context": "string"}],
    "tags": ["string"],
    "confidence": 0.0,
}


def build_prompt(
    metadata: dict[str, str | None],
    text: str,
    preset: str,
    max_input_chars: int,
) -> str:
    template = PRESETS.get(preset, DEFAULT_TEMPLATE)
    truncated_text = text[:max_input_chars]
    if len(text) > max_input_chars:
        truncated_text += "\n[...truncated]"

    meta_lines = [
        f"title: {metadata.get('title') or ''}",
        f"url: {metadata.get('url') or ''}",
        f"feed: {metadata.get('feed_title') or 'direct'}",
        f"published: {metadata.get('published') or 'unknown'}",
    ]
    meta_block = "\n".join(meta_lines)
    schema_json = json.dumps(SUMMARY_SCHEMA, indent=2)

    return (
        f"{template.format(schema=schema_json)}\n"
        f"Prompt version: {PROMPT_VERSION}\n\n"
        f"Article metadata:\n{meta_block}\n\n"
        f"Article content:\n{truncated_text}\n"
    )
