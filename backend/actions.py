from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class PendingAction:
    id: str
    description: str
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_actions: dict[str, PendingAction] = {}


def create_action(description: str) -> PendingAction:
    action = PendingAction(id=str(uuid4()), description=description)
    _actions[action.id] = action
    return action


def list_actions() -> list[PendingAction]:
    return list(_actions.values())


def update_action(action_id: str, status: ActionStatus) -> PendingAction | None:
    action = _actions.get(action_id)
    if action is None or action.status is not ActionStatus.PENDING:
        return None
    action.status = status
    return action
