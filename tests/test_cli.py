from __future__ import annotations

from click.testing import CliRunner

from distill_feed.cli import cli


def test_cli_digest_dry_run_exit_zero(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "digest",
            "--url",
            "https://example.com/post",
            "--dry-run",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--out",
            str(tmp_path / "digest.md"),
        ],
    )
    assert result.exit_code == 0
    assert list(tmp_path.glob("digest-*.md"))


def test_cli_invalid_config_still_exit_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "--concurrency", "0"])
    assert result.exit_code == 0
