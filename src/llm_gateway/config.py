"""Environment-only configuration. Nothing secret has a default value."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from llm_gateway.errors import ConfigError

MAX_PROMPT_CHARS = 16_000


class Settings(BaseSettings):
    """Runtime settings loaded from the environment and an optional .env file."""

    model_config = SettingsConfigDict(
        env_prefix="LLM_GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8080
    api_key: str = ""
    log_level: str = "INFO"
    log_prompts: bool = False
    enable_docs: bool | None = None

    provider_api_key: str = ""
    provider_base_url: str = "https://api.openai.com/v1"
    model_fast: str = "gpt-4o-mini"
    model_strong: str = "gpt-4o"
    model_fallback: str = "gpt-4o-mini"
    request_timeout_seconds: float = Field(default=30, gt=0, le=120)

    s3_bucket: str = ""
    s3_prefix: str = "llm-gateway/cache/"
    s3_region: str = "us-east-1"
    s3_expected_owner: str = ""
    cache_ttl_seconds: int = Field(default=3600, ge=1)
    cache_dir: str = ".cache/llm-gateway"

    guardrails_enabled: bool = True
    block_on_secret: bool = True
    block_on_injection: bool = True
    redact_pii: bool = True
    fast_tier_max_chars: int = Field(default=800, ge=1)
    max_prompt_chars: int = Field(default=MAX_PROMPT_CHARS, ge=1, le=MAX_PROMPT_CHARS)
    rate_limit_rpm: int = Field(default=60, ge=1, le=10_000)
    trust_proxy: bool = False
    otlp_endpoint: str = ""

    def allowlist(self) -> set[str]:
        return {name for name in (self.model_fast, self.model_strong, self.model_fallback) if name}

    def docs_enabled(self) -> bool:
        if self.enable_docs is None:
            return self.env != "production"
        return self.enable_docs

    def check(self) -> None:
        """Fail closed before the process accepts traffic in production."""
        if self.env != "production":
            return
        if len(self.api_key) < 32:
            raise ConfigError(
                "LLM_GATEWAY_API_KEY must be at least 32 characters when LLM_GATEWAY_ENV=production"
            )
        if not self.provider_api_key:
            raise ConfigError("LLM_GATEWAY_PROVIDER_API_KEY is required when LLM_GATEWAY_ENV=production")
