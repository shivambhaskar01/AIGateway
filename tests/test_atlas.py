from llm_gateway.routing.atlas import Atlas
from tests.conftest import make_settings


def test_short_prompt_uses_fast_tier(tmp_path):
    route = Atlas(make_settings(tmp_path)).route("Explain pooling.", "auto", None)
    assert route.tier == "fast"
    assert route.models[0] == "fast-model"
    assert "fallback-model" in route.models


def test_code_and_length_use_strong_tier(tmp_path):
    atlas = Atlas(make_settings(tmp_path))
    code = atlas.route("```python\nprint(1)\n```", "auto", None)
    long_prompt = atlas.route("x" * 801, "auto", None)
    forced = atlas.route("x" * 801, "fast", None)
    assert code.tier == "strong"
    assert long_prompt.tier == "strong"
    assert forced.tier == "fast"


def test_unknown_model_is_rejected(tmp_path):
    from llm_gateway.errors import GatewayError
    import pytest

    with pytest.raises(GatewayError) as caught:
        Atlas(make_settings(tmp_path)).route("hello", "auto", "gpt-unlisted")
    assert caught.value.code == "model_not_allowed"
