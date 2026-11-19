from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from modules.meetings.appointment_manager import AppointmentManager
from modules.meetings.appointment_notifier import AppointmentNotifier
from modules.meetings.message_sender import SimulatedMessageSender
from modules.meetings.planning_routes import conflict_detector, simulated_agenda
from modules.meetings.routes import appointment_detector, meetings_service


router = APIRouter(prefix="/meetings", tags=["meetings-appointments"])

appointment_manager = AppointmentManager(
    meetings_service=meetings_service,
    agenda_source=simulated_agenda,
    conflict_detector=conflict_detector,
)
appointment_notifier = AppointmentNotifier(meetings_service=meetings_service, sender=SimulatedMessageSender())



class AppointmentAccept(BaseModel):
    time: Optional[str] = None
    duration_minutes: Optional[int] = None
    ignore_conflicts: bool = False


class MessageSend(BaseModel):
    confirm: bool
    body: Optional[str] = None



def check_result(result, missing_message):

    if result is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    if result is False:
        raise HTTPException(status_code=404, detail=missing_message)

    return result


@router.post("/{meeting_id}/appointments/detect")
def detect_appointments(meeting_id: str):

    try:
        result = appointment_detector.detect(meeting_id=meeting_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible, réessaie dans une minute.")

    return check_result(result=result, missing_message="Réunion introuvable.")


@router.get("/{meeting_id}/appointments")
def list_appointments(meeting_id: str):

    appointments = check_result(
        result=appointment_manager.list_appointments(meeting_id=meeting_id),
        missing_message="Réunion introuvable.",
    )

    return {"appointments": appointments}


@router.post("/{meeting_id}/appointments/{appointment_id}/accept")
def accept_appointment(meeting_id: str, appointment_id: str, request: AppointmentAccept):

    try:
        result = appointment_manager.accept(
            meeting_id=meeting_id,
            appointment_id=appointment_id,
            time=request.time,
            duration_minutes=request.duration_minutes,
            ignore_conflicts=request.ignore_conflicts,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return check_result(result=result, missing_message="Rendez-vous introuvable.")


@router.post("/{meeting_id}/appointments/{appointment_id}/reject")
def reject_appointment(meeting_id: str, appointment_id: str):

    try:
        result = appointment_manager.reject(meeting_id=meeting_id, appointment_id=appointment_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return check_result(result=result, missing_message="Rendez-vous introuvable.")


@router.get("/{meeting_id}/appointments/{appointment_id}/message")
def get_appointment_message(meeting_id: str, appointment_id: str):

    try:
        result = appointment_notifier.build_draft(meeting_id=meeting_id, appointment_id=appointment_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return check_result(result=result, missing_message="Rendez-vous introuvable.")


@router.post("/{meeting_id}/appointments/{appointment_id}/message/send")
def send_appointment_message(meeting_id: str, appointment_id: str, request: MessageSend):

    if not request.confirm:
        raise HTTPException(status_code=403, detail="Envoi annulé : il faut confirmer l'envoi (confirm à true).")

    try:
        result = appointment_notifier.send(meeting_id=meeting_id, appointment_id=appointment_id, body=request.body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return check_result(result=result, missing_message="Rendez-vous introuvable.")