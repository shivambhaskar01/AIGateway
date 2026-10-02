"""Atlas: choose a model tier, then a fallback chain inside the allowlist."""

import re
from dataclasses import dataclass

from llm_gateway.config import Settings
from llm_gateway.errors import GatewayError

_CODE_LINE = re.compile(r"(?m)^\s*(def |class |function |import |package |#include |public class )")
_CODE_MARKERS = ("```", "traceback", "stack trace", "syntax error", "refactor this", "compile error")
_REASONING_MARKERS = (
    "step by step",
    "chain of thought",
    "trade-off",
    "tradeoff",
    "system design",
    "architecture review",
)


@dataclass(frozen=True)
class Route:
    tier: str
    reason: str
    models: tuple[str, ...]


class Atlas:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(self, prompt: str, tier: str, model: str | None) -> Route:
        if model and model not in self.settings.allowlist():
            raise GatewayError(400, "model_not_allowed", extra={"model": model})
        chosen, reason = self._tier(prompt, tier)
        return Route(chosen, reason, tuple(self._chain(chosen, model)))

    def _tier(self, prompt: str, tier: str) -> tuple[str, str]:
        if tier == "fast":
            return "fast", "caller selected the fast tier"
        if tier == "strong":
            return "strong", "caller selected the strong tier"
        if len(prompt) > self.settings.fast_tier_max_chars:
            return "strong", "prompt length exceeded the fast-tier budget"
        lowered = prompt.lower()
        if "```" in prompt or _CODE_LINE.search(prompt) or any(marker in lowered for marker in _CODE_MARKERS):
            return "strong", "code markers selected the strong tier"
        if any(marker in lowered for marker in _REASONING_MARKERS):
            return "strong", "reasoning markers selected the strong tier"
        return "fast", "short conversational prompt selected the fast tier"

    def _chain(self, tier: str, override: str | None) -> list[str]:
        if tier == "strong":
            base = [self.settings.model_strong, self.settings.model_fast, self.settings.model_fallback]
        else:
            base = [self.settings.model_fast, self.settings.model_fallback]
        if override:
            base = [override, *base]
        chain: list[str] = []
        for name in base:
            if name and name not in chain:
                chain.append(name)
        return chain
