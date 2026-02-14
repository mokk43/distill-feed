# Distill-Feed

Distill-Feed is a Python CLI that builds a single Markdown digest from RSS/Atom feeds and direct article URLs.

It is designed for non-interactive agent workflows:
- deterministic output shape
- machine-readable JSON run report (`--json`)
- resilient execution (`exit 0` even on partial/total failures, with failures reported in output)

## What It Does

`distill-feed digest`:
1. Ingests candidates from feeds and direct URLs.
2. Normalizes and deduplicates URLs globally.
3. Selects items by date (`--since`) with a global cap (`--max-items`).
4. Fetches article HTML and extracts readability-style main content.
5. Summarizes with an LLM endpoint:
   - OpenAI-compatible mode: Responses API first, then automatic fallback to Chat Completions if unsupported
   - Gemini native mode: `generateContent` when using
     `https://generativelanguage.googleapis.com/v1beta` (non-`/openai` path)
   - OpenAI-compatible Gemini paths (for example `.../v1beta/openai`) stay on Responses/Chat routing
6. Writes one Markdown digest file with date suffix:
   - `digest-YYYYMMDD.md` (derived from `--out` base path)
7. Optionally writes a JSON run report to stdout (`--json`).

## CLI

Primary command:

```bash
distill-feed digest [OPTIONS]
```

### Input options

- `--feed <url>` (repeatable)
- `--feeds-file <path>` (one URL per line; blank lines and `#` comments ignored)
- `--url <url>` (repeatable)
- `--urls-file <path>` (one URL per line; blank lines and `#` comments ignored)
- `--since <RFC3339|YYYY-MM-DD>`
- `--max-items <N>` (global cap across feeds + direct URLs)

### Output options

- `--out <path>` base path (default `./digest.md`, writes with date suffix)
- `--json` emit run report JSON to stdout

### LLM options

- `--base-url <url>`
- `--api-key <key>` (optional if provided by env or `.env`)
- `--model <name>`
- `--temperature <float>`
- `--max-output-tokens <N>`
- `--prompt-preset <name>`

Gemini example:

```bash
distill-feed digest \
  --url https://example.com/post \
  --base-url https://generativelanguage.googleapis.com/v1beta \
  --model gemini-2.0-flash \
  --api-key "$DISTILL_FEED_API_KEY"
```

### Runtime options

- `--timeout <seconds>`
- `--concurrency <N>`
- `--cache-dir <path>`
- `--dry-run` (no LLM calls; reports selected/skipped plan)
- `--verbose`

## Configuration

Resolution order:

```text
CLI flag > environment variable > .env file > default
```

`.env` loading behavior:
- `.env` loaded from current working directory
- existing process environment is not overridden (`override=False`)

API key semantics:
- `--api-key` may be omitted if `DISTILL_FEED_API_KEY` exists in env or `.env`
- without any API key:
  - `--dry-run` is valid
  - non-dry-run records missing-credential failures in digest/report and still exits `0`

## Outputs

### Markdown digest

Single output file per run:
- `{out_stem}-YYYYMMDD{out_suffix}`

Digest structure includes:
- header with run timestamp, input summary, LLM config (`base_url`, `model`, `llm_api_used`, `prompt_version`), success/failure counts
- stable per-article sections
- tail section with skipped and failed items + reasons

### JSON run report (`--json`)

A single JSON object to stdout with stable keys:
- `run_id`, `timestamp`
- `inputs`
- `selection`
- `llm` (`api_used` values are stable: `responses|chat_completions`)
- `items` (statuses: `selected|summarized|skipped|failed`)
- aggregate counts

Human logs go to stderr.

## Reliability and Error Policy

- CLI always exits with code `0`.
- Failures are surfaced via digest tail, JSON report, and stderr logs.
- Per-item failure isolation: one bad item does not stop the run.
- API keys are never logged.

## Planned Architecture

See:
- `/Users/gary/git/distill-feed/docs/PRD.md`
- `/Users/gary/git/distill-feed/docs/ARCHITECTURE.md`

Key modules (planned):
- `cli.py`, `config.py`, `pipeline.py`
- ingestion: feed parsing, URL normalization, selection
- extraction: fetch + readability extraction
- summarization: LLM client, prompts, schema validation
- output: markdown writer + JSON report
- file-based cache

## Milestones

- `M0`: CLI skeleton + config/env + markdown writer (no LLM)
- `M1`: fetch + extraction + direct-URL summarization
- `M2`: RSS ingestion + ranking/filtering + global cap
- `M3`: cache + retry/backoff + concurrency + JSON report
- `M4`: hardening and provider quirks

## License

MIT. See `/Users/gary/git/distill-feed/LICENSE`.
