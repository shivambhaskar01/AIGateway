"""Relay: one attempt per model. SDK retries stay off so each attempt is visible."""

from dataclasses import dataclass

from llm_gateway.errors import LLMNotConfigured


@dataclass(frozen=True)
class RelayResult:
    output: str
    model: str
    attempts: tuple[str, ...]
    fallback_used: bool


class ProviderFailure(Exception):
    def __init__(self, code: str, attempts: list[str]) -> None:
        super().__init__(code)
        self.code = code
        self.attempts = attempts


class Relay:
    def __init__(self, client) -> None:
        self.client = client

    async def run(
        self,
        models: tuple[str, ...],
        *,
        prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> RelayResult:
        attempts: list[str] = []
        for model in models:
            attempts.append(model)
            try:
                text = await self.client.complete(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            except LLMNotConfigured:
                raise ProviderFailure("llm_not_configured", attempts) from None
            except Exception:
                continue
            if text and str(text).strip():
                return RelayResult(str(text), model, tuple(attempts), len(attempts) > 1)
        raise ProviderFailure("provider_unavailable", attempts)
