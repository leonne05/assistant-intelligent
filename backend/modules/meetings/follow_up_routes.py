from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from modules.meetings.action_tracker import ActionTracker
from modules.meetings.reminder_builder import ReminderBuilder
from modules.meetings.routes import meetings_service, report_manager, spoken_text_builder


router = APIRouter(prefix="/follow-up", tags=["follow-up-actions"])

action_tracker = ActionTracker(meetings_service=meetings_service)
reminder_builder = ReminderBuilder(meetings_service=meetings_service, action_tracker=action_tracker)



@router.get("/actions")
def list_actions(who: Optional[str] = None, status: str = Query("open", pattern="^(open|done|all)$")):
    return {"actions": action_tracker.collect(who=who, status=status), "counts": action_tracker.count()}


@router.get("/reminders")
def get_reminders(who: Optional[str] = None, days_ahead: int = Query(3, ge=0, le=60)):
    return reminder_builder.build(who=who, days_ahead=days_ahead)


@router.get("/reminders/spoken-text")
def get_reminders_spoken_text(who: Optional[str] = None, days_ahead: int = Query(3, ge=0, le=60)):
    reminders = reminder_builder.build(who=who, days_ahead=days_ahead)

    return {"spoken_text": spoken_text_builder.build(markdown=reminders["text"])}


@router.post("/actions/{meeting_id}/{action_id}/done")
def mark_action_done(meeting_id: str, action_id: str):

    try:
        action = report_manager.update_action(meeting_id=meeting_id, action_id=action_id, status="done")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if action is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    if action is False:
        raise HTTPException(status_code=404, detail="Action introuvable.")

    return action