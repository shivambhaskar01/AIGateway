"""Redact common personal data before a prompt is forwarded or logged."""

import re

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

_TOKENS = {
    "email": "[REDACTED_EMAIL]",
    "ssn": "[REDACTED_SSN]",
    "payment_card": "[REDACTED_PAYMENT_CARD]",
}


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Return masked text and the finding names, in scan order, without duplicates."""
    names: list[str] = []
    masked = _apply(text, _EMAIL, "email", names)
    masked = _apply(masked, _SSN, "ssn", names)
    masked = _apply_cards(masked, names)
    return masked, names


def _apply(text: str, pattern: re.Pattern[str], name: str, names: list[str]) -> str:
    if pattern.search(text):
        names.append(name)
        return pattern.sub(_TOKENS[name], text)
    return text


def _apply_cards(text: str, names: list[str]) -> str:
    found = False

    def replace(match: re.Match[str]) -> str:
        nonlocal found
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            found = True
            return _TOKENS["payment_card"]
        return match.group(0)

    masked = _CARD.sub(replace, text)
    if found:
        names.append("payment_card")
    return masked


def _luhn(number: str) -> bool:
    total = 0
    reverse = number[::-1]
    for index, character in enumerate(reverse):
        digit = int(character)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
