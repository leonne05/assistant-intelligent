from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationMemory:
    def __init__(self, max_messages: int = 20) -> None:
        self._messages: deque[Message] = deque(maxlen=max_messages)
        self._preferences: dict[str, str] = {}

    def add(self, role: Role, content: str) -> Message:
        message = Message(role=role, content=content)
        self._messages.append(message)
        return message

    def messages(self) -> list[Message]:
        return list(self._messages)

    def set_preference(self, key: str, value: str) -> None:
        self._preferences[key] = value

    def preferences(self) -> dict[str, str]:
        return dict(self._preferences)


memory = ConversationMemory()
