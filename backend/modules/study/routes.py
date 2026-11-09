from datetime import date
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from modules.study.audio_splitter import AudioSplitter
from modules.study.exporter import StudyExporter
from modules.study.long_audio import LongAudioProcessor
from modules.study.service import StudyService


router = APIRouter(prefix="/study", tags=["study"])
study_service = StudyService()
study_exporter = StudyExporter()
long_audio_processor = LongAudioProcessor(study_service=study_service, splitter=AudioSplitter())



class AskRequest(BaseModel):
    text_interaction: str



class EventDecision(BaseModel):
    status: Literal["approved", "rejected"]



class QuizRequest(BaseModel):
    question_count: int = Field(default=5, ge=1, le=10)
    topics: Optional[List[str]] = None



class QuizAnswers(BaseModel):
    answers: List[Optional[int]]



@router.get("/ping")
def ping():
    return study_service.get_status()


@router.post("/ask")
def ask(request: AskRequest):

    try:
        result = study_service.ask_llm(text_interaction=request.text_interaction)
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible, réessaie dans une minute.")

    return result


@router.get("/history")
def get_history(limit: int = 20):
    return {"messages": study_service.get_history(limit=limit)}


@router.delete("/history")
def clear_history():
    study_service.clear_history()
    return {"cleared": True}


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


@router.post("/courses/{course_id}/chunks")
def transcribe_chunk(
    course_id: str,
    chunk_index: str = Form(""),
    audio_file: UploadFile = File(...),
    user_consent: bool = Form(...),
):
    audio_bytes = audio_file.file.read()

    if chunk_index.strip() and not chunk_index.strip().isdigit():
        raise HTTPException(status_code=400, detail="Le numéro du morceau doit être un nombre entier.")

    if chunk_index.strip():
        chunk_number = int(chunk_index)
    else:
        course = study_service.get_course_transcript(course_id=course_id)
        chunk_number = course["chunk_count"] + 1 if course else 1

    try:
        result = study_service.transcribe_chunk(
            course_id=course_id,
            chunk_index=chunk_number,
            audio_file_name=audio_file.filename,
            audio_bytes=audio_bytes,
            user_consent=user_consent,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return result


@router.post("/courses/{course_id}/audio")
def upload_long_audio(
    course_id: str,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    user_consent: bool = Form(...),
):
    audio_bytes = audio_file.file.read()

    try:
        long_audio_processor.prepare(
            course_id=course_id,
            audio_file_name=audio_file.filename,
            audio_bytes=audio_bytes,
            user_consent=user_consent,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    background_tasks.add_task(
        long_audio_processor.process,
        course_id=course_id,
        audio_file_name=audio_file.filename,
        audio_bytes=audio_bytes,
    )

    return {"course_id": course_id, "status": "splitting"}


@router.get("/courses/{course_id}/audio")
def get_long_audio_status(course_id: str):
    status = long_audio_processor.get_status(course_id=course_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Aucun audio long en cours pour ce cours.")

    return status


@router.get("/courses")
def list_courses():
    return {"courses": study_service.list_courses()}


@router.delete("/courses/{course_id}")
def delete_course(course_id: str):
    deleted = study_service.delete_course(course_id=course_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "deleted": True}


@router.get("/courses/{course_id}/transcript")
def get_course_transcript(course_id: str):
    course = study_service.get_course_transcript(course_id=course_id)

    if course is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "transcript": course["transcript"], "chunk_count": course["chunk_count"]}


@router.post("/courses/{course_id}/summary")
def summarize_course(course_id: str):

    try:
        summary = study_service.summarize_course(course_id=course_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service de résumé est indisponible, réessaie dans une minute.")

    if summary is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "summary": summary}


@router.post("/courses/{course_id}/pdf")
def upload_course_pdf(course_id: str, background_tasks: BackgroundTasks, pdf_file: UploadFile = File(...)):
    pdf_bytes = pdf_file.file.read()

    try:
        pdf_groups = study_service.prepare_pdf(
            course_id=course_id,
            pdf_file_name=pdf_file.filename,
            pdf_bytes=pdf_bytes,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    background_tasks.add_task(study_service.process_pdf, course_id=course_id, pdf_groups=pdf_groups)

    return {"course_id": course_id, "status": "processing", "group_count": len(pdf_groups)}


@router.get("/courses/{course_id}/pdf")
def get_course_pdf(course_id: str):
    pdf = study_service.get_pdf_status(course_id=course_id)

    if pdf is None:
        raise HTTPException(status_code=404, detail="Aucun PDF pour ce cours.")

    return pdf


@router.post("/courses/{course_id}/events/detect")
def detect_course_events(course_id: str):

    try:
        new_events = study_service.detect_course_events(course_id=course_id)
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible, réessaie dans une minute.")

    if new_events is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "new_events": new_events}


@router.get("/courses/{course_id}/events")
def get_course_events(course_id: str):
    events = study_service.get_events(course_id=course_id)

    if events is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "events": events}


@router.patch("/courses/{course_id}/events/{event_id}")
def decide_course_event(course_id: str, event_id: str, decision: EventDecision):

    try:
        event = study_service.decide_event(course_id=course_id, event_id=event_id, status=decision.status)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if event is None:
        raise HTTPException(status_code=404, detail="Cours ou événement introuvable.")

    return event


@router.post("/courses/{course_id}/quiz")
def create_quiz(course_id: str, request: QuizRequest):

    try:
        quiz = study_service.generate_quiz(
            course_id=course_id,
            question_count=request.question_count,
            topics=request.topics,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible ou le quiz est invalide, réessaie dans une minute.")

    if quiz is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return quiz


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: str):
    quiz = study_service.get_quiz(quiz_id=quiz_id)

    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz introuvable.")

    return quiz


@router.post("/quizzes/{quiz_id}/answers")
def correct_quiz(quiz_id: str, request: QuizAnswers):

    try:
        correction = study_service.correct_quiz(quiz_id=quiz_id, answers=request.answers)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if correction is None:
        raise HTTPException(status_code=404, detail="Quiz introuvable.")

    return correction


@router.get("/gaps")
def get_gaps(course_id: Optional[str] = None):
    return {"gaps": study_service.get_gaps(course_id=course_id)}


@router.delete("/gaps")
def clear_gaps():
    study_service.clear_gaps()
    return {"cleared": True}


@router.get("/revision")
def get_revision_plan(course_id: Optional[str] = None, on_date: Optional[str] = None):

    try:
        plan_date = date.fromisoformat(on_date) if on_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="La date doit être au format AAAA-MM-JJ, par exemple 2026-11-10.")

    return study_service.get_revision_plan(course_id=course_id, on_date=plan_date)


@router.get("/courses/{course_id}/export")
def export_course(
    course_id: str,
    file_format: str = Query("pdf", alias="format"),
    content: str = "summary",
):
    course = study_service.get_course_transcript(course_id=course_id)

    if course is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    try:
        exported = study_exporter.export(
            course_id=course_id,
            course=course,
            file_format=file_format or "pdf",
            content=content or "summary",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return Response(
        content=exported["data"],
        media_type=exported["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{exported["file_name"]}"'},
    )