"""Mask secrets and personal data inside structured log events."""

from llm_gateway.guardrails.pii import redact_pii
from llm_gateway.guardrails.secrets import mask_secrets


def redact_event(_logger, _method, event_dict: dict) -> dict:
    return {key: _scrub(value) for key, value in event_dict.items()}


def _scrub(value, depth: int = 0):
    if depth > 4:
        return value
    if isinstance(value, str):
        masked, _names = redact_pii(mask_secrets(value))
        return masked
    if isinstance(value, dict):
        return {key: _scrub(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item, depth + 1) for item in value]
    return value
