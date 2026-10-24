from __future__ import annotations

from enum import StrEnum


class Intent(StrEnum):
    CHAT = "chat"
    ACTION = "action"
    UNKNOWN = "unknown"


def detect_intent(text: str) -> Intent:
    normalized = text.casefold()
    action_markers = (
        "envoie",
        "envoie un",
        "supprime",
        "ouvre",
        "lance",
        "exécute",
        "execute",
        "crée",
        "cree",
    )
    if any(marker in normalized for marker in action_markers):
        return Intent.ACTION
    if normalized.strip():
        return Intent.CHAT
    return Intent.UNKNOWN
