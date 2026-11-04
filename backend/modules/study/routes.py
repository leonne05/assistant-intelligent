from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from modules.study.service import StudyService


router = APIRouter(prefix="/study", tags=["study"])
study_service = StudyService()



class AskRequest(BaseModel):
    text_interaction: str



@router.get("/ping")
def ping():
    return study_service.get_status()


@router.post("/ask")
def ask(request: AskRequest):
    response = study_service.ask_llm(text_interaction=request.text_interaction)
    return {"response": response}


@router.post("/transcribe")
def transcribe(audio_file: UploadFile = File(...), user_consent: bool = Form(...)):
    audio_bytes = audio_file.file.read()

    try:
        transcript = study_service.transcribe_course(
            audio_file_name=audio_file.filename,
            audio_bytes=audio_bytes,
            user_consent=user_consent,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {"transcript": transcript}