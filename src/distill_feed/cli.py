from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from pydantic import ValidationError

from distill_feed.config import Config
from distill_feed.output.report import emit_report
from distill_feed.pipeline import run


USAGE_GUIDE = """Usage:
  distill-feed digest [OPTIONS]

Examples:
  distill-feed digest --feed https://example.com/rss --max-items 5
  distill-feed digest --feeds-file feeds.txt --since 2026-02-01 --out digest-output/digest.md
  distill-feed digest --url https://example.com/post --dry-run --json

Tips:
  - Use --help (or -h) to see all options.
  - --feed/--feeds-file and --url/--urls-file can be combined.
  - Output file name is date-suffixed automatically.
"""


def _read_urls_file(path: Path | None) -> list[str]:
    if path is None:
        return []
    values: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        values.append(line)
    return values


def _show_usage(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return
    click.echo(USAGE_GUIDE)
    ctx.exit(0)


@click.group(
    context_settings={"help_option_names": ["--help", "-h"]},
    invoke_without_command=True,
)
@click.option(
    "--usage",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_show_usage,
    help="Show usage guide and examples.",
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Distill feed entries into a Markdown digest."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command(
    "digest",
    context_settings={"help_option_names": ["--help", "-h"]},
    help="Build a digest from feed and article URLs.",
)
@click.option(
    "--usage",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_show_usage,
    help="Show usage guide and examples.",
)
@click.option("--feed", "feed_urls", multiple=True, help="RSS/Atom feed URL (repeatable).")
@click.option(
    "--feeds-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="File containing feed URLs (one per line).",
)
@click.option("--url", "direct_urls", multiple=True, help="Direct article URL (repeatable).")
@click.option(
    "--urls-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="File containing direct URLs (one per line).",
)
@click.option("--since", default=None, help="RFC3339 or YYYY-MM-DD cutoff for dated items.")
@click.option("--max-items", type=int, default=None, help="Global max items across all sources.")
@click.option("--out", type=click.Path(path_type=Path), default=None, help="Markdown output base path.")
@click.option("--json", "json_output", is_flag=True, default=None, help="Emit run report JSON.")
@click.option("--base-url", default=None, help="OpenAI-compatible base URL.")
@click.option("--api-key", default=None, help="API key (prefer env/.env).")
@click.option("--model", default=None, help="Model identifier.")
@click.option("--temperature", type=float, default=None, help="Sampling temperature 0.0-2.0.")
@click.option("--max-output-tokens", type=int, default=None, help="Max output tokens.")
@click.option("--prompt-preset", default=None, help="Prompt preset.")
@click.option("--timeout", type=float, default=None, help="Timeout seconds for network calls.")
@click.option("--concurrency", type=int, default=None, help="Concurrency for processing.")
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Cache directory path.",
)
@click.option("--dry-run", is_flag=True, default=None, help="Skip LLM calls, report planned work.")
@click.option("--verbose", is_flag=True, default=None, help="Verbose stderr logs.")
def digest(  # noqa: PLR0913
    feed_urls: tuple[str, ...],
    feeds_file: Path | None,
    direct_urls: tuple[str, ...],
    urls_file: Path | None,
    since: str | None,
    max_items: int | None,
    out: Path | None,
    json_output: bool | None,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    temperature: float | None,
    max_output_tokens: int | None,
    prompt_preset: str | None,
    timeout: float | None,
    concurrency: int | None,
    cache_dir: Path | None,
    dry_run: bool | None,
    verbose: bool | None,
) -> None:
    load_dotenv(override=False)

    logging.basicConfig(
        level=logging.DEBUG if bool(verbose) else logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(message)s",
    )

    feeds = list(feed_urls) + _read_urls_file(feeds_file)
    urls = list(direct_urls) + _read_urls_file(urls_file)

    overrides: dict[str, object] = {"feeds": feeds, "urls": urls}
    optional_values = {
        "since": since,
        "max_items": max_items,
        "out": out,
        "json_output": json_output,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "prompt_preset": prompt_preset,
        "timeout": timeout,
        "concurrency": concurrency,
        "cache_dir": cache_dir,
        "dry_run": dry_run,
        "verbose": verbose,
    }
    for key, value in optional_values.items():
        if value is not None:
            overrides[key] = value

    try:
        config = Config(**overrides)
    except ValidationError as exc:
        click.echo(f"configuration error: {exc}", err=True)
        return

    try:
        report = asyncio.run(run(config))
        if config.json_output:
            emit_report(report)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"pipeline error: {exc}", err=True)


def main() -> int:
    try:
        cli.main(standalone_mode=False)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"fatal error: {exc}", err=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
