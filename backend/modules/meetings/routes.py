from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from typing import List

from modules.meetings.service import MeetingsService


router = APIRouter(prefix="/meetings", tags=["meetings"])
meetings_service = MeetingsService()



class AskRequest(BaseModel):
    text_interaction: str



class MeetingRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    participants: List[str] = []
    agenda: List[str] = []



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