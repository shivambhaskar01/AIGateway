"""Airlock: gateway authentication. The provider key is never this credential."""

import hashlib
import hmac

from llm_gateway.config import Settings


class Airlock:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def bearer(self, header: str | None) -> str | None:
        if not header:
            return None
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        return token.strip()

    def verify(self, token: str | None) -> bool:
        expected = self.settings.api_key
        if not expected or not token:
            return False
        return hmac.compare_digest(token, expected)

    def fingerprint(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def client_ip(self, request) -> str:
        if self.settings.trust_proxy:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"
