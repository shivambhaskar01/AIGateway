"""Detect credentials before they leave the process or land in a log line.

Matches are reported by rule name. Callers receive a masked string, never the
secret, in API bodies and logs.
"""

import re
from dataclasses import dataclass

REDACTED_SECRET = "[REDACTED_SECRET]"

@dataclass(frozen=True)
class SecretHit:
    name: str
    start: int
    end: int


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("github_fine_grained_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("provider_secret", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_\-]{16,}\b")),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
            r"[\s\S]+?"
            r"-----END (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
        ),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    (
        "labeled_secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|aws_secret_access_key)"
            r"\s*[=:]\s*['\"]?[A-Za-z0-9_\-./+=]{12,}"
        ),
    ),
)


def find_secrets(text: str) -> list[SecretHit]:
    hits: list[SecretHit] = []
    for name, pattern in _RULES:
        for match in pattern.finditer(text):
            hits.append(SecretHit(name, match.start(), match.end()))
    return hits


def mask_secrets(text: str) -> str:
    return _mask_spans(text, [(hit.start, hit.end) for hit in find_secrets(text)], REDACTED_SECRET)


def _mask_spans(text: str, spans: list[tuple[int, int]], token: str) -> str:
    if not spans:
        return text
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    pieces: list[str] = []
    cursor = 0
    for start, end in merged:
        pieces.append(text[cursor:start])
        pieces.append(token)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)
