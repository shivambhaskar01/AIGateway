"""Errors that are safe to surface. Messages never include prompts or secrets."""


class ConfigError(Exception):
    """Startup configuration is incomplete for the selected environment."""


class LLMNotConfigured(Exception):
    """No provider credential is available. Fallback must not continue."""


class GatewayError(Exception):
    """A handled request failure with a stable error code."""

    def __init__(self, status_code: int, code: str, extra: dict | None = None) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.extra = extra or {}
