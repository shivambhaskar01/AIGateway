import asyncio

import pytest

from llm_gateway.errors import LLMNotConfigured
from llm_gateway.llm.langchain_client import coerce_content
from llm_gateway.llm.relay import ProviderFailure, Relay
from tests.conftest import ScriptedLLM


class Boom(Exception):
    pass


class Unconfigured:
    def __init__(self):
        self.calls = 0

    async def complete(self, *, model, prompt, temperature, max_tokens, timeout):
        self.calls += 1
        raise LLMNotConfigured()


def test_fallback_skips_failed_primary():
    llm = ScriptedLLM([Boom(), "recovered"])
    result = asyncio.run(Relay(llm).run(("strong", "fast"), prompt="hi", temperature=0, max_tokens=8, timeout=1))
    assert result.fallback_used is True
    assert result.model == "fast"
    assert result.attempts == ("strong", "fast")


def test_missing_provider_key_stops_the_chain():
    llm = Unconfigured()
    with pytest.raises(ProviderFailure) as caught:
        asyncio.run(Relay(llm).run(("strong", "fast"), prompt="hi", temperature=0, max_tokens=8, timeout=1))
    assert caught.value.code == "llm_not_configured"
    assert llm.calls == 1


def test_content_blocks_are_joined():
    assert coerce_content([{"type": "text", "text": "hello"}, " there"]) == "hello there"
