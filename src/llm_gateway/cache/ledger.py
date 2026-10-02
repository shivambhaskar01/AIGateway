"""Ledger: response cache. The prompt is never stored; the object key is a hash."""

import hashlib
import json
import re
import time
from pathlib import Path

_HEX = re.compile(r"^[a-f0-9]{64}$")


def cache_key(*, tier: str, models: tuple[str, ...], prompt: str, temperature: float, max_tokens: int) -> str:
    canonical = json.dumps(
        {
            "max_tokens": max_tokens,
            "models": models,
            "prompt": prompt,
            "temperature": temperature,
            "tier": tier,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class LocalLedger:
    """Process-local file cache used when no bucket is configured."""

    backend = "local"

    def __init__(self, directory: str, ttl_seconds: int) -> None:
        self.directory = Path(directory)
        self.ttl_seconds = ttl_seconds
        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["expires_at"] <= time.time():
            path.unlink(missing_ok=True)
            return None
        return payload["value"]

    def set(self, key: str, value: dict) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"expires_at": time.time() + self.ttl_seconds, "value": value})
        temporary = path.with_suffix(".tmp")
        temporary.write_text(body, encoding="utf-8")
        temporary.replace(path)

    def _path(self, key: str) -> Path:
        if not _HEX.fullmatch(key):
            raise ValueError("cache key must be a sha256 hex digest")
        return self.directory / key[:2] / f"{key}.json"


def build_ledger(settings):
    if not settings.s3_bucket:
        return LocalLedger(settings.cache_dir, settings.cache_ttl_seconds)
    from llm_gateway.cache.s3 import S3Ledger
    from llm_gateway.errors import ConfigError

    ledger = S3Ledger(
        bucket=settings.s3_bucket,
        prefix=settings.s3_prefix,
        ttl_seconds=settings.cache_ttl_seconds,
        region=settings.s3_region,
        expected_owner=settings.s3_expected_owner,
    )
    try:
        ledger.probe()
    except Exception as exc:
        if settings.env == "production":
            raise ConfigError("S3 cache probe failed") from exc
        return LocalLedger(settings.cache_dir, settings.cache_ttl_seconds)
    return ledger
