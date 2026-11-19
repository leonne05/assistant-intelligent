from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from modules.agenda_source import SimulatedAgenda
from modules.meetings.agenda_editor import AgendaEditor
from modules.meetings.conflict_detector import ConflictDetector
from modules.meetings.meeting_scheduler import MeetingScheduler
from modules.meetings.preparation_builder import PreparationBuilder
from modules.meetings.routes import meetings_service, spoken_text_builder


router = APIRouter(prefix="/meetings", tags=["meetings-preparation"])
agenda_router = APIRouter(prefix="/agenda-simulated", tags=["agenda-simulated"])

simulated_agenda = SimulatedAgenda()
conflict_detector = ConflictDetector(agenda_source=simulated_agenda, meetings_service=meetings_service)
meeting_scheduler = MeetingScheduler(
    meetings_service=meetings_service,
    agenda_source=simulated_agenda,
    conflict_detector=conflict_detector,
)
agenda_editor = AgendaEditor(meetings_service=meetings_service)
preparation_builder = PreparationBuilder(meetings_service=meetings_service, conflict_detector=conflict_detector)



class EventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    start: str
    end: str


class ScheduleRequest(BaseModel):
    start: str
    duration_minutes: Optional[int] = None


class AgendaConfirm(BaseModel):
    confirm: bool


class AgendaPoints(BaseModel):
    points: List[str]


class AgendaPoint(BaseModel):
    point: str
    position: Optional[int] = None



@agenda_router.post("/events")
def add_simulated_event(request: EventRequest):

    try:
        return simulated_agenda.add_event(title=request.title, start=request.start, end=request.end)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@agenda_router.get("/events")
def list_simulated_events():
    return {"events": sorted(simulated_agenda.events, key=lambda event: event["start"])}


@agenda_router.delete("/events/{event_id}")
def delete_simulated_event(event_id: str):

    if not simulated_agenda.delete_event(event_id=event_id):
        raise HTTPException(status_code=404, detail="Événement introuvable.")

    return {"deleted": event_id}


@router.post("/{meeting_id}/schedule")
def schedule_meeting(meeting_id: str, request: ScheduleRequest):

    try:
        schedule = meeting_scheduler.schedule(
            meeting_id=meeting_id, start=request.start, duration_minutes=request.duration_minutes
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if schedule is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return schedule


@router.get("/{meeting_id}/schedule")
def get_meeting_schedule(meeting_id: str):

    try:
        schedule = meeting_scheduler.get_schedule(meeting_id=meeting_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if schedule is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return schedule


@router.post("/{meeting_id}/schedule/agenda")
def add_meeting_to_agenda(meeting_id: str, request: AgendaConfirm):

    if not request.confirm:
        raise HTTPException(status_code=403, detail="Ajout annulé : il faut confirmer (confirm à true).")

    try:
        schedule = meeting_scheduler.add_to_agenda(meeting_id=meeting_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if schedule is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return schedule


@router.put("/{meeting_id}/agenda")
def set_agenda_points(meeting_id: str, request: AgendaPoints):

    try:
        points = agenda_editor.set_points(meeting_id=meeting_id, points=request.points)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if points is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return {"agenda": points}


@router.post("/{meeting_id}/agenda/points")
def add_agenda_point(meeting_id: str, request: AgendaPoint):

    try:
        points = agenda_editor.add_point(meeting_id=meeting_id, point=request.point, position=request.position)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if points is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return {"agenda": points}


@router.delete("/{meeting_id}/agenda/points/{position}")
def remove_agenda_point(meeting_id: str, position: int):

    try:
        points = agenda_editor.remove_point(meeting_id=meeting_id, position=position)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if points is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return {"agenda": points}


@router.get("/{meeting_id}/preparation")
def get_preparation(meeting_id: str):

    sheet = preparation_builder.build(meeting_id=meeting_id)

    if sheet is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return sheet


@router.get("/{meeting_id}/preparation/spoken-text")
def get_preparation_spoken_text(meeting_id: str):

    sheet = preparation_builder.build(meeting_id=meeting_id)

    if sheet is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return {"meeting_id": meeting_id, "spoken_text": spoken_text_builder.build(markdown=sheet["text"])}