from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from typing import List, Optional

from modules.meetings.long_audio import MeetingAudioProcessor
from modules.meetings.message_sender import SimulatedMessageSender
from modules.meetings.report_manager import ReportManager
from modules.meetings.service import MeetingsService
from modules.speech import SpokenTextBuilder
from modules.study.audio_splitter import AudioSplitter
from modules.study.exporter import StudyExporter


router = APIRouter(prefix="/meetings", tags=["meetings"])
meetings_service = MeetingsService()
meeting_audio_processor = MeetingAudioProcessor(meetings_service=meetings_service, splitter=AudioSplitter())
spoken_text_builder = SpokenTextBuilder()
report_manager = ReportManager(
    meetings_service=meetings_service,
    exporter=StudyExporter(),
    sender=SimulatedMessageSender(),
)



class AskRequest(BaseModel):
    text_interaction: str



class MeetingRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    participants: List[str] = []
    agenda: List[str] = []



class ReportEdit(BaseModel):
    text: Optional[str] = None
    decisions: Optional[List[str]] = None
    open_points: Optional[List[str]] = None



class ReportCorrection(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)



class ActionCreate(BaseModel):
    who: str = ""
    what: str
    due: Optional[str] = None



class ActionEdit(BaseModel):
    who: Optional[str] = None
    what: Optional[str] = None
    due: Optional[str] = None
    status: Optional[str] = None



class ReportSend(BaseModel):
    confirm: bool
    recipients: Optional[List[str]] = None



class ConsentDecision(BaseModel):
    participant: str
    accepted: bool



@router.get("/ping")
def ping():
    return meetings_service.get_status()


@router.post("/ask")
def ask(request: AskRequest):
    response = meetings_service.ask_llm(text_interaction=request.text_interaction)
    return {"response": response}


@router.post("")
def create_meeting(request: MeetingRequest):

    try:
        return meetings_service.create_meeting(
            title=request.title,
            participants=request.participants,
            agenda=request.agenda,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("")
def list_meetings():
    return {"meetings": meetings_service.list_meetings()}


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str):
    meeting = meetings_service.get_meeting(meeting_id=meeting_id)

    if meeting is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return meeting


@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: str):

    if not meetings_service.delete_meeting(meeting_id=meeting_id):
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return {"deleted": meeting_id}


@router.post("/{meeting_id}/consent")
def set_consent(meeting_id: str, decision: ConsentDecision):

    try:
        meeting = meetings_service.set_consent(
            meeting_id=meeting_id,
            participant_name=decision.participant,
            accepted=decision.accepted,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if meeting is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return meeting


@router.post("/{meeting_id}/chunks")
def transcribe_chunk(
    meeting_id: str,
    audio_file: UploadFile = File(...),
    user_consent: bool = Form(...),
    chunk_index: str = Form(""),
):
    audio_bytes = audio_file.file.read()

    if chunk_index.strip() and not chunk_index.strip().isdigit():
        raise HTTPException(status_code=400, detail="Le numéro du morceau doit être un nombre entier.")

    try:
        result = meetings_service.transcribe_chunk(
            meeting_id=meeting_id,
            audio_file_name=audio_file.filename,
            audio_bytes=audio_bytes,
            user_consent=user_consent,
            chunk_index=int(chunk_index) if chunk_index.strip() else None,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if result is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return result


@router.post("/{meeting_id}/audio")
def upload_meeting_audio(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    user_consent: bool = Form(...),
    auto_report: bool = Form(True),
):
    audio_bytes = audio_file.file.read()

    try:
        job = meeting_audio_processor.prepare(
            meeting_id=meeting_id,
            audio_file_name=audio_file.filename,
            audio_bytes=audio_bytes,
            user_consent=user_consent,
            auto_report=auto_report,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if job is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    background_tasks.add_task(
        meeting_audio_processor.process,
        meeting_id=meeting_id,
        audio_file_name=audio_file.filename,
        audio_bytes=audio_bytes,
    )

    return {"meeting_id": meeting_id, **job}


@router.get("/{meeting_id}/audio")
def get_meeting_audio_status(meeting_id: str):
    status = meeting_audio_processor.get_status(meeting_id=meeting_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Aucun audio envoyé pour cette réunion.")

    return {"meeting_id": meeting_id, **status}


@router.post("/{meeting_id}/report")
def generate_report(meeting_id: str):

    try:
        report = meetings_service.generate_report(meeting_id=meeting_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service de compte rendu est indisponible, réessaie dans une minute.")

    if report is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return report


@router.get("/{meeting_id}/report")
def get_report(meeting_id: str):
    meeting = meetings_service.get_meeting(meeting_id=meeting_id)

    if meeting is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    if meeting["report"] is None:
        raise HTTPException(status_code=404, detail="Cette réunion n'a pas encore de compte rendu.")

    return meeting["report"]


@router.patch("/{meeting_id}/report")
def edit_report(meeting_id: str, request: ReportEdit):

    try:
        report = report_manager.edit(
            meeting_id=meeting_id,
            text=request.text,
            decisions=request.decisions,
            open_points=request.open_points,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if report is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return report


@router.post("/{meeting_id}/report/correct")
def correct_report(meeting_id: str, request: ReportCorrection):

    try:
        report = report_manager.correct(meeting_id=meeting_id, instruction=request.instruction)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible, réessaie dans une minute.")

    if report is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return report


@router.post("/{meeting_id}/report/actions")
def add_report_action(meeting_id: str, request: ActionCreate):

    try:
        action = report_manager.add_action(
            meeting_id=meeting_id,
            who=request.who,
            what=request.what,
            due=request.due,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if action is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return action


@router.patch("/{meeting_id}/report/actions/{action_id}")
def update_report_action(meeting_id: str, action_id: str, request: ActionEdit):

    try:
        action = report_manager.update_action(
            meeting_id=meeting_id,
            action_id=action_id,
            who=request.who,
            what=request.what,
            due=request.due,
            status=request.status,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if action is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    if action is False:
        raise HTTPException(status_code=404, detail="Action introuvable.")

    return action


@router.delete("/{meeting_id}/report/actions/{action_id}")
def delete_report_action(meeting_id: str, action_id: str):

    try:
        deleted = report_manager.delete_action(meeting_id=meeting_id, action_id=action_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if deleted is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    if deleted is False:
        raise HTTPException(status_code=404, detail="Action introuvable.")

    return {"meeting_id": meeting_id, "action_id": action_id, "deleted": True}


@router.post("/{meeting_id}/report/validate")
def validate_report(meeting_id: str):

    try:
        report = report_manager.validate(meeting_id=meeting_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if report is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return report


@router.post("/{meeting_id}/report/send")
def send_report(meeting_id: str, request: ReportSend):

    if not request.confirm:
        raise HTTPException(status_code=403, detail="Envoi annulé : il faut confirmer l'envoi (confirm à true).")

    try:
        result = report_manager.send(meeting_id=meeting_id, recipients=request.recipients)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if result is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return result


@router.get("/{meeting_id}/outbox")
def get_outbox(meeting_id: str):
    outbox = report_manager.get_outbox(meeting_id=meeting_id)

    if outbox is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return {"meeting_id": meeting_id, "messages": outbox}


@router.get("/{meeting_id}/report/export")
def export_report(meeting_id: str, file_format: str = Query("pdf", alias="format")):

    try:
        exported = report_manager.export(meeting_id=meeting_id, file_format=file_format or "pdf")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if exported is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return Response(
        content=exported["data"],
        media_type=exported["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{exported["file_name"]}"'},
    )


@router.post("/{meeting_id}/report/approve")
def approve_and_send_report(meeting_id: str, request: ReportSend):

    if not request.confirm:
        raise HTTPException(status_code=403, detail="Envoi annulé : il faut confirmer l'envoi (confirm à true).")

    try:
        result = report_manager.approve_and_send(meeting_id=meeting_id, recipients=request.recipients)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if result is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return result


@router.get("/{meeting_id}/report/spoken-text")
def get_report_spoken_text(meeting_id: str):

    try:
        meeting, report = report_manager.get_meeting_and_report(meeting_id=meeting_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if meeting is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable.")

    return {"meeting_id": meeting_id, "spoken_text": spoken_text_builder.build(markdown=report["text"])}