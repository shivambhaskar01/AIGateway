"""High-precision prompt-injection rules.

Each rule is sufficient to block. Patterns are intentionally narrow so ordinary
instructions such as "act as a reviewer" are not treated as an attack.
"""

import re
from dataclasses import dataclass

@dataclass(frozen=True)
class InjectionHit:
    name: str


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules|messages)",
            re.IGNORECASE,
        ),
    ),
    (
        "policy_disregard",
        re.compile(r"\bdisregard\b.{0,40}\b(system|instructions|policy|rules)\b", re.IGNORECASE),
    ),
    (
        "context_wipe",
        re.compile(r"\bforget\b.{0,30}\b(everything|all|previous|above)\b", re.IGNORECASE),
    ),
    (
        "system_exfiltration",
        re.compile(
            r"(reveal|print|show|repeat|dump)\s+(your\s+)?(system|hidden|developer)\s+(prompt|message|instructions)",
            re.IGNORECASE,
        ),
    ),
    (
        "delimiter_smuggle",
        re.compile(r"<\|im_start\|>|<\|im_end\|>|\[INST\]|<<SYS>>", re.IGNORECASE),
    ),
    (
        "role_hijack",
        re.compile(r"\byou\s+are\s+now\b|\bnew\s+instructions\s*:", re.IGNORECASE),
    ),
    (
        "policy_bypass",
        re.compile(r"\bdo anything now\b|\bdan mode\b|\benable developer mode\b", re.IGNORECASE),
    ),
    (
        "encoded_follow",
        re.compile(
            r"base64[,:]?\s*decode|decode\s+this\s+and\s+(run|follow|execute)",
            re.IGNORECASE,
        ),
    ),
)


def find_injections(text: str) -> list[InjectionHit]:
    found: list[InjectionHit] = []
    seen: set[str] = set()
    for name, pattern in _RULES:
        if name not in seen and pattern.search(text):
            seen.add(name)
            found.append(InjectionHit(name))
    return found
