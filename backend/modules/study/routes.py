from fastapi import APIRouter
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