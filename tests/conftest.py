from fastapi.testclient import TestClient

from llm_gateway.config import Settings
from llm_gateway.main import create_app


class ScriptedLLM:
    def __init__(self, script: list):
        self.script = list(script)
        self.calls: list[str] = []
        self.prompts: list[str] = []

    async def complete(self, *, model, prompt, temperature, max_tokens, timeout):
        self.calls.append(model)
        self.prompts.append(prompt)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_settings(tmp_path, **overrides) -> Settings:
    data = {
        "_env_file": None,
        "env": "test",
        "api_key": "test-gateway-key-0123456789abcdef",
        "provider_api_key": "",
        "cache_dir": str(tmp_path / "cache"),
        "cache_ttl_seconds": 3600,
        "rate_limit_rpm": 1000,
        "log_level": "ERROR",
        "model_fast": "fast-model",
        "model_strong": "strong-model",
        "model_fallback": "fallback-model",
    }
    data.update(overrides)
    return Settings(**data)


def make_client(tmp_path, llm, **overrides):
    settings = make_settings(tmp_path, **overrides)
    app = create_app(settings, llm=llm)
    return TestClient(app), llm


AUTH = {"Authorization": "Bearer test-gateway-key-0123456789abcdef"}
