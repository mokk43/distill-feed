from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class Config(BaseModel):
    model_config = ConfigDict(extra="ignore")

    feeds: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    since: str | None = None
    max_items: int | None = None

    out: Path = Path("./digest.md")
    json_output: bool = False

    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_output_tokens: int = 1024
    prompt_preset: str = "default"
    max_input_chars: int = 12_000

    timeout: float = 30.0
    concurrency: int = 4
    retries: int = 3
    cache_dir: Path = Path("~/.cache/distill-feed/")
    cache_max_html_bytes: int = 5 * 1024 * 1024

    dry_run: bool = False
    verbose: bool = False

    @model_validator(mode="before")
    @classmethod
    def apply_env_defaults(cls, data: object) -> object:
        load_dotenv(override=False)
        values = dict(data) if isinstance(data, dict) else {}

        env_map = {
            "base_url": "DISTILL_FEED_BASE_URL",
            "api_key": "DISTILL_FEED_API_KEY",
            "model": "DISTILL_FEED_MODEL",
            "temperature": "DISTILL_FEED_TEMPERATURE",
            "max_output_tokens": "DISTILL_FEED_MAX_OUTPUT_TOKENS",
            "timeout": "DISTILL_FEED_TIMEOUT",
            "concurrency": "DISTILL_FEED_CONCURRENCY",
            "cache_dir": "DISTILL_FEED_CACHE_DIR",
            "out": "DISTILL_FEED_OUT",
            "prompt_preset": "DISTILL_FEED_PROMPT_PRESET",
            "max_input_chars": "DISTILL_FEED_MAX_INPUT_CHARS",
            "retries": "DISTILL_FEED_RETRIES",
            "cache_max_html_bytes": "DISTILL_FEED_CACHE_MAX_HTML_BYTES",
        }
        for field_name, env_name in env_map.items():
            if field_name not in values or values[field_name] is None:
                env_value = os.getenv(env_name)
                if env_value not in (None, ""):
                    values[field_name] = env_value
        return values

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if not (0.0 <= value <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return value

    @field_validator("concurrency")
    @classmethod
    def validate_concurrency(cls, value: int) -> int:
        if value < 1:
            raise ValueError("concurrency must be >= 1")
        return value

    @field_validator("max_items")
    @classmethod
    def validate_max_items(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("max_items must be >= 1")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("base_url must be an absolute http(s) URL")
        return value.rstrip("/")

    @field_validator("cache_dir", mode="before")
    @classmethod
    def expand_cache_dir(cls, value: str | Path) -> Path:
        return Path(value).expanduser()

    @field_validator("out", mode="before")
    @classmethod
    def normalize_out(cls, value: str | Path) -> Path:
        return Path(value)

    def api_key_value(self) -> str | None:
        if self.api_key is None:
            return None
        return self.api_key.get_secret_value()
