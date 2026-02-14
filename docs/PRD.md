# Distill-Feed — Product Requirements Document (PRD)

- **Project**: `distill-feed`
- **Owner**: Gary Chang
- **License**: MIT
- **Last updated**: 2026-02-14
- **Status**: Draft (implementation-ready)

## 1. Summary
Build a **Python CLI** that ingests blog articles (from **RSS/Atom feeds** and/or explicit **URLs**), fetches and performs **readability-style extraction** to obtain the main article text, summarizes each article using an **OpenAI-compatible API** (**Responses API first**, with automatic fallback to **Chat Completions**), and writes a **single combined Markdown digest** (`digest.md`) containing a **run timestamp** plus per-article summaries. The CLI is designed to be invoked by **AI agents / agent skills** (non-interactive, stable output, optional machine-readable report).

## 2. Goals / Non-goals

### 2.1 Goals
- **Agent-friendly CLI**: non-interactive by default; predictable outputs; optional JSON run report.
- **Provider-agnostic LLM**: supports OpenAI-compatible endpoints via configurable `base_url`.
- **Good article extraction**: readability-style main content extraction suitable for common blogs/news sites.
- **Single output artifact**: one `digest.md` per run, with consistent structure and timestamp.

### 2.2 Non-goals (v1)
- Browser automation / JS rendering (e.g., Playwright) as a default requirement.
- Paywall bypassing.
- A web UI.
- Per-article output files (only one combined digest).

## 3. Users & Use Cases
- **Human**: “Summarize the newest items from my feed list into a daily digest.”
- **AI agent / skill**: “Run the CLI, read `digest.md`, parse JSON report to decide next actions.”

## 4. CLI Requirements

### 4.1 Primary command
`distill-feed digest`

#### Inputs
- `--feed <url>` (repeatable): RSS/Atom feed URLs.
- `--feeds-file <path>`: one feed URL per line; supports blank lines and `# comments`.
- `--url <url>` (repeatable): direct article URLs.
- `--urls-file <path>`: one URL per line; supports blank lines and `# comments`.
- `--since <RFC3339|YYYY-MM-DD>`:
  - If an item has a known `published`/`updated` date and it is older than `since`, **exclude** it.
  - If an item has **no** date, **include** it (do not exclude due to missing date).
- `--max-items <N>`: maximum number of articles to summarize **total across all feeds + direct URLs**.

#### Output
- Output artifact filename must include a run date suffix: `YYYYMMDD`.
- `--out <path>`: output path **base** for markdown.
  - Default base: `./digest.md`
  - The CLI writes: `./digest-YYYYMMDD.md` (date derived from run timestamp; UTC recommended)
- **Single output file only** (no per-article files).
- Digest includes a **run timestamp** in the header (UTC recommended).
- `--json`: emit machine-readable run report JSON to **stdout** (markdown still written to `--out`).

#### LLM options
- `--base-url <url>`: OpenAI-compatible API base URL (e.g. `https://api.openai.com/v1`).
- `--api-key <key>`: API key (prefer env var; CLI flag overrides).
- `--model <name>`: model identifier string.
- `--temperature <float>`: default low (e.g. 0.2).
- `--max-output-tokens <N>`: cap summary length.
- `--prompt-preset <name>`: select a built-in prompt style (optional; supports future customization).

#### Defaults from `.env`
- If a `.env` file exists (in the current working directory), load it to populate default environment variables **before** resolving configuration.
- `.env` values should not override already-set process environment variables (existing env wins).

#### Runtime / reliability
- `--timeout <seconds>`: network timeout for fetch + LLM calls.
- `--concurrency <N>`: parallelism for fetch/extract/summarize (default modest, e.g. 4).
- `--cache-dir <path>`: cache directory (default e.g. `~/.cache/distill-feed/`).
- `--dry-run`: do not call LLM; list selected items and reasons.
- `--verbose`: more logs to stderr (never print API keys).

### 4.2 Exit code policy
- **Always exit with code `0`**, including partial and total failures.
- All errors are surfaced via:
  - written `digest.md` failure sections, and/or
  - `--json` run report, and/or
  - stderr logs.

> Rationale: agent pipelines should not break on transient failures; downstream logic should consult the run report.

## 5. Ingestion & Selection Logic

### 5.1 Feed parsing
For each feed item, capture:
- `feed_title`
- `title`
- `link` (article URL)
- `published` and/or `updated` (if available)
- `author` (if available)

### 5.2 URL normalization & deduplication
- Normalize URLs for dedupe (scheme/host casing, trailing slashes, common tracking params optionally).
- Deduplicate across all sources by normalized URL.

### 5.3 Ranking & filtering
- Combine candidates from feeds and direct URLs.
- Sort primarily by best-available date:
  - `sort_date = published || updated || None`
  - Items with dates appear first, newest-to-oldest.
  - Items without dates appear after dated items, in a stable deterministic order (e.g. by URL).
- Apply `--since`:
  - If dated and older than `since`: exclude.
  - If undated: include.
- Apply `--max-items` after sorting, as a **global total cap**.

## 6. Content Fetching & Extraction

### 6.1 Fetch
- HTTP GET the article URL with:
  - redirect support
  - timeout
  - retry with backoff for transient errors (e.g., 429/5xx)
  - a clear User-Agent

### 6.2 Readability-style extraction
- Use readability-style main-content extraction to obtain:
  - extracted title (fallback to feed title/item title)
  - cleaned main content (text; optional minimal markdown conversion)
- Compute and record a lightweight extraction quality signal (e.g., extracted text length, ratio of text to markup).

### 6.3 Caching
Cache artifacts (by URL hash) to improve speed and reproducibility:
- fetched HTML (optional; size-limited)
- extracted text
- derived metadata

## 7. LLM Summarization

### 7.1 API compatibility strategy
1. **Responses API first**:
   - `POST {base_url}/v1/responses`
2. **Fallback to Chat Completions** when Responses is not supported:
   - `POST {base_url}/v1/chat/completions`
   - Trigger fallback on clear “unsupported” responses (e.g., 404/405) or provider-specific “not supported” error signatures.

Run report must indicate which API path was ultimately used (`responses` vs `chat_completions`).

### 7.2 Prompting & output contract
- Provide article metadata + extracted text to the model.
- Enforce token budgeting:
  - hard cap/truncation of input text
  - ensure instructions remain intact
- Require model output to be **strict JSON** following a fixed schema (to keep markdown generation deterministic).

Example schema:
```json
{
  "title": "string",
  "one_sentence": "string",
  "summary_bullets": ["string"],
  "key_takeaways": ["string"],
  "why_it_matters": ["string"],
  "notable_quotes": [{"quote": "string", "context": "string"}],
  "tags": ["string"],
  "confidence": 0.0
}
```

If the model output is invalid JSON, perform one repair attempt (model-assisted JSON repair) and otherwise mark the item as failed with a parse error (still included in digest report).

### 7.3 Prompt versioning
- Maintain a `prompt_version` identifier.
- Include `prompt_version` in:
  - `digest.md` header
  - JSON run report
  - cache keys for summaries

## 8. Output: Markdown Digest (`digest.md`)

### 8.1 Header (top of file)
Must include:
- Run timestamp (UTC recommended)
- Input sources summary (feed count, URL count, items selected)
- LLM configuration summary (safe fields only: `base_url`, `model`, `llm_api_used`, `prompt_version`)
- Success/failure counts

### 8.2 Per-article section (stable structure)
For each selected item:
- `## {Article Title}`
  - Source: `{url}`
  - Feed: `{feed_title | "direct"}`
  - Published: `{date | "unknown"}`
  - Extraction: `{quality note}`
  - One sentence: …
  - Summary:
    - …
  - Key takeaways:
    - …
  - Why it matters:
    - …
  - Quotes (optional):
    - “…” — …
  - Tags (optional): `tag1, tag2`

### 8.3 Tail: Run report section
At end of file, include a concise list of:
- skipped items (and reason)
- failed items (error type + brief message)

## 9. Machine-readable Run Report (`--json`)
When `--json` is set:
- Write structured JSON to **stdout** (single JSON object).
- Write human logs to **stderr**.

Report fields (minimum):
- `run_id`, `timestamp`
- `inputs`: feeds, urls (counts; optionally lists)
- `selection`: total_selected, since, max_items
- `llm`: base_url, model, api_used (`responses|chat_completions`), prompt_version
- `items`: array of per-item records with status:
  - `selected|summarized|skipped|failed`
  - url, title, feed_title, date
  - timing breakdown: fetch/extract/summarize durations
  - error info (if any)
  - token usage (if returned by provider)

## 10. Security & Privacy
- Never log API keys.
- Avoid logging full extracted article text unless explicitly requested (`--verbose` may still redact).
- Cache directory must not store secrets.

## 11. Acceptance Criteria (v1)
- Given a feeds file and `--max-items 10`, the CLI writes `digest-YYYYMMDD.md` with up to 10 article sections and a timestamp header.
- `--since` excludes older items **only when dated**; undated items remain eligible.
- `--max-items` applies **globally** across all feeds and direct URLs.
- LLM integration uses **Responses first** and automatically falls back to **Chat Completions** when Responses is unsupported.
- `--dry-run` performs **no** LLM calls and clearly reports planned selection.
- CLI exits with **code 0** even on failures; failures are visible in markdown/run report.

## 12. Milestones
- **M0**: CLI skeleton + config/env + markdown writer (no LLM).
- **M1**: URL fetch + readability extraction + LLM summarize for direct URLs.
- **M2**: RSS ingestion + global ranking + `--since` + global `--max-items`.
- **M3**: caching + retry/backoff + concurrency + `--json` report.
- **M4**: hardening (dedupe improvements, more extraction heuristics, provider quirks).

