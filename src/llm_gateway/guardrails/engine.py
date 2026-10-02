"""Sentinel pipeline.

Input is normalized, scanned, and either blocked or rewritten before any
provider client is constructed. Model output is scanned for credentials so a
completion cannot carry a key back to the caller or into Ledger.
"""

import unicodedata
from dataclasses import dataclass

from llm_gateway.guardrails.injection import find_injections
from llm_gateway.guardrails.pii import redact_pii
from llm_gateway.guardrails.secrets import find_secrets, mask_secrets


@dataclass(frozen=True)
class Finding:
    kind: str
    name: str
    action: str


@dataclass(frozen=True)
class Verdict:
    action: str
    text: str
    findings: tuple[Finding, ...]

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "findings": [
                {"kind": item.kind, "name": item.name, "action": item.action}
                for item in self.findings
            ],
        }


class Sentinel:
    def __init__(
        self,
        *,
        enabled: bool = True,
        block_on_secret: bool = True,
        block_on_injection: bool = True,
        redact_pii_enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.block_on_secret = block_on_secret
        self.block_on_injection = block_on_injection
        self.redact_pii_enabled = redact_pii_enabled

    def scan_input(self, text: str) -> Verdict:
        normalized = normalize(text)
        if not self.enabled:
            return Verdict("allow", normalized, ())

        findings: list[Finding] = []
        blocked = False
        for hit in find_injections(normalized):
            action = "block" if self.block_on_injection else "observe"
            findings.append(Finding("injection", hit.name, action))
            blocked = blocked or self.block_on_injection

        secret_hits = find_secrets(normalized)
        for hit in _unique_names(secret_hits):
            action = "block" if self.block_on_secret else "redact"
            findings.append(Finding("secret", hit, action))
            blocked = blocked or self.block_on_secret

        if blocked:
            return Verdict("block", "", tuple(findings))

        cleaned = mask_secrets(normalized) if secret_hits else normalized
        if self.redact_pii_enabled:
            cleaned, pii_names = redact_pii(cleaned)
            findings.extend(Finding("pii", name, "redact") for name in pii_names)
        return Verdict("allow", cleaned, tuple(findings))

    def scan_output(self, text: str) -> Verdict:
        """Stop credentials produced by a model from being returned or cached."""
        hits = find_secrets(text)
        if not hits:
            return Verdict("allow", text, ())
        findings = tuple(
            Finding("secret", name, "block" if self.block_on_secret else "redact")
            for name in _unique_names(hits)
        )
        if self.block_on_secret:
            return Verdict("block", "", findings)
        return Verdict("allow", mask_secrets(text), findings)


def normalize(text: str) -> str:
    """NFKC plus null stripping closes a class of trivial filter bypasses."""
    return unicodedata.normalize("NFKC", text).replace("\x00", "")


def _unique_names(hits: list) -> list[str]:
    names: list[str] = []
    for hit in hits:
        if hit.name not in names:
            names.append(hit.name)
    return names
