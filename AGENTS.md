# AGENTS.md

This file defines implementation guidance for AI/coding agents working in this repository.

## Scope

- Project: `distill-feed`
- Canonical product requirements: `/Users/gary/git/distill-feed/docs/PRD.md`
- Canonical architecture: `/Users/gary/git/distill-feed/docs/ARCHITECTURE.md`
- If this file conflicts with PRD/architecture, follow PRD first, then architecture.

## Product Contract (Do Not Break)

- Build a non-interactive Python CLI: `distill-feed digest`.
- Always write one combined Markdown digest output file per run, with date suffix:
  - `{out_stem}-YYYYMMDD{out_suffix}`
- Keep digest markdown read-friendly and article-focused, with stable per-article structure.
- Optionally emit machine-readable run report JSON to stdout (`--json`).
- Keep human logs on stderr.
- Always exit with code `0`, even when there are failures.
- Errors must be visible in report/logs.

## Required CLI Semantics

- Support feed and URL inputs:
  - `--feed`, `--feeds-file`, `--url`, `--urls-file`
- For `--feeds-file` and `--urls-file`:
  - one URL per line
  - ignore blank lines
  - ignore lines starting with `#`
- Selection rules:
  - deduplicate by normalized URL across all sources
  - sort dated items newest-first, then undated in deterministic order
  - `--since` excludes only dated items older than threshold
  - undated items remain eligible
  - `--max-items` is a global cap across all sources

## LLM and Summarization Contract

- Use configurable `base_url` with two routing modes:
  - OpenAI-compatible mode: call Responses API first, fallback to Chat Completions on unsupported signals (e.g., 404/405/signature).
  - Gemini native mode: if host is `generativelanguage.googleapis.com` and path is not OpenAI-compatible (`.../openai`), call `models/{model}:generateContent`.
- Record final API path used as `responses` or `chat_completions` in report (keep this stable for compatibility).
- Prompt output must be strict JSON matching the summary schema.
- On invalid JSON, attempt one repair call; if still invalid, mark item failed.
- Track `prompt_version` and include it in report and summary cache keying.

## API Key and Env Rules

- Config precedence must be:
  - CLI flag > environment variable > `.env` > default
- Load `.env` from current working directory with no override of existing env.
- `--api-key` is optional if provided via env/`.env`.
- Missing API key behavior:
  - allowed for `--dry-run` (no LLM calls)
  - non-dry-run should mark summarization attempts failed with clear credential error
  - still exit `0`

## Output and Report Rules

- Digest markdown should include only summarized article sections:
  - title heading
  - source URL and published date
  - one-sentence summary
  - `Summary`, `Key takeaways`, and `Why it matters` paragraph blocks
  - optional notable quotes
- Keep run metadata, skipped items, and failed-item reasons in JSON report/logs.
- JSON report must be one object with stable keys and item-level statuses:
  - statuses: `selected`, `summarized`, `skipped`, `failed`
  - include skip/failure reasons
  - include timing breakdown and token usage when available

## Reliability and Security

- Never log API keys.
- Avoid logging full extracted content by default.
- Use timeout, retries/backoff, and bounded concurrency (including Gemini native LLM HTTP calls).
- Keep per-item failures isolated; never fail whole run due to one item.
- Cache only non-secret data (html, extracted text, metadata, summaries).

## Implementation Plan (Target Modules)

- `src/distill_feed/cli.py`
- `src/distill_feed/config.py`
- `src/distill_feed/models.py`
- `src/distill_feed/pipeline.py`
- `src/distill_feed/cache.py`
- `src/distill_feed/ingestion/{feed_parser.py,url_normalize.py,selector.py}`
- `src/distill_feed/extraction/{fetcher.py,extractor.py}`
- `src/distill_feed/summarization/{llm_client.py,prompts.py,schemas.py}`
- `src/distill_feed/output/{markdown.py,report.py}`

## Testing Expectations

- Use pytest (+ pytest-asyncio where needed).
- Mock HTTP and LLM calls for deterministic tests.
- Cover:
  - selection semantics (`--since`, undated behavior, global cap)
  - fallback Responses -> Chat Completions
  - Gemini routing (native vs OpenAI-compatible endpoint path)
  - retry/backoff behavior on retryable LLM HTTP errors
  - digest naming and structure
  - `--dry-run` no-LLM path
  - always-exit-0 behavior
  - JSON report schema and statuses (including stable `llm.api_used` values)

## Change Discipline

- Keep behavior deterministic and agent-friendly.
- Prefer explicit schemas over untyped dict payloads.
- Preserve backward-compatible output shape unless requirements explicitly change.
- Update docs when behavior/contract changes:
  - `/Users/gary/git/distill-feed/docs/PRD.md`
  - `/Users/gary/git/distill-feed/docs/ARCHITECTURE.md`
  - `/Users/gary/git/distill-feed/README.md`
