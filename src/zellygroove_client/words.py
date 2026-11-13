"""The client's own messages in Korean or English (English support, 2026-11-13).

The language is, first, STUDIO_LANG (ko or en), which the client also sends to the service; then the account's, learned
from the service (its answers say Content-Language: en for an account read in English, nothing for Korean) and kept with
the saved token; before either is known, this computer's own locale. What the service says comes in its language already."""
import os

LANGUAGES = ("ko", "en")
_learned: str | None = None


def chosen() -> str | None:
    value = os.environ.get("STUDIO_LANG", "").strip().lower()
    return value if value in LANGUAGES else None


def learn(language: str | None) -> None:
    global _learned
    if language in LANGUAGES:
        _learned = language


def language() -> str:
    found = chosen() or _learned
    if found:
        return found
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name, "")
        if value:
            return "ko" if value.lower().startswith("ko") else "en"
    return "ko"


def say(korean: str, english: str) -> str:
    return english if language() == "en" else korean
