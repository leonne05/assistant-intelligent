from datetime import date
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from modules.study.audio_splitter import AudioSplitter
from modules.study.exporter import StudyExporter
from modules.study.lessons import LessonProcessor
from modules.study.long_audio import LongAudioProcessor
from modules.study.revision_offers import RevisionOfferManager
from modules.study.revision_planner import RevisionPlanner
from modules.study.service import StudyService
from modules.study.subjects import SubjectManager


router = APIRouter(prefix="/study", tags=["study"])
study_service = StudyService()
study_exporter = StudyExporter()
long_audio_processor = LongAudioProcessor(study_service=study_service, splitter=AudioSplitter())
subject_manager = SubjectManager(study_service=study_service)
lesson_processor = LessonProcessor(study_service=study_service, long_audio_processor=long_audio_processor)
revision_planner = RevisionPlanner(
    study_service=study_service,
    subject_manager=subject_manager,
    study_exporter=study_exporter,
)
revision_offers = RevisionOfferManager(study_service=study_service, revision_planner=revision_planner)



class AskRequest(BaseModel):
    text_interaction: str



class EventDecision(BaseModel):
    status: Literal["approved", "rejected"]



class QuizRequest(BaseModel):
    question_count: int = Field(default=5, ge=1, le=10)
    topics: Optional[List[str]] = None



class QuizAnswers(BaseModel):
    answers: List[Optional[int]]



class SubjectRequest(BaseModel):
    name: str



class CourseSubject(BaseModel):
    subject: str
    lesson_number: Optional[int] = None



class RevisionPlanRequest(BaseModel):
    exam_date: str
    minutes_per_day: int = 60
    start_date: Optional[str] = None



class RevisionAnswer(BaseModel):
    accept: bool
    minutes_per_day: int = 60



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

    return {**event, "revision_offer": revision_offers.get_offer(course_id=course_id, event=event)}


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


@router.post("/subjects")
def create_subject(request: SubjectRequest):

    try:
        subject = subject_manager.create_subject(name=request.name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return subject


@router.get("/subjects")
def list_subjects():
    return subject_manager.list_subjects()


@router.delete("/subjects/{subject}")
def delete_subject(subject: str, delete_lessons: bool = False):

    try:
        deleted = subject_manager.delete_subject(name=subject, delete_lessons=delete_lessons)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if deleted is None:
        raise HTTPException(status_code=404, detail="Matière introuvable.")

    return deleted


@router.post("/subjects/{subject}/lessons")
def add_lesson(
    subject: str,
    background_tasks: BackgroundTasks,
    audio_file: Optional[UploadFile] = File(None),
    pdf_file: Optional[UploadFile] = File(None),
    user_consent: bool = Form(False),
    lesson_number: str = Form(""),
):
    if lesson_number.strip() and not lesson_number.strip().isdigit():
        raise HTTPException(status_code=400, detail="Le numéro de la leçon doit être un nombre entier.")

    audio_bytes = audio_file.file.read() if audio_file is not None and audio_file.filename else b""
    pdf_bytes = pdf_file.file.read() if pdf_file is not None and pdf_file.filename else b""

    try:
        lesson = subject_manager.add_lesson(
            subject=subject,
            lesson_number=int(lesson_number) if lesson_number.strip() else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    course_id = lesson["course_id"]
    pdf_groups = []

    try:
        if audio_bytes:
            long_audio_processor.prepare(
                course_id=course_id,
                audio_file_name=audio_file.filename,
                audio_bytes=audio_bytes,
                user_consent=user_consent,
            )

        if pdf_bytes:
            pdf_groups = study_service.prepare_pdf(
                course_id=course_id,
                pdf_file_name=pdf_file.filename,
                pdf_bytes=pdf_bytes,
            )
    except (PermissionError, ValueError) as error:
        long_audio_processor.jobs.pop(course_id, None)
        study_service.delete_course(course_id=course_id)

        if isinstance(error, PermissionError):
            raise HTTPException(status_code=403, detail=str(error))

        raise HTTPException(status_code=400, detail=str(error))

    if audio_bytes or pdf_groups:
        background_tasks.add_task(
            lesson_processor.process,
            course_id=course_id,
            audio_file_name=audio_file.filename if audio_bytes else None,
            audio_bytes=audio_bytes,
            pdf_groups=pdf_groups,
        )

    return {
        **lesson,
        "status": "processing" if (audio_bytes or pdf_groups) else "empty",
        "has_audio": bool(audio_bytes),
        "has_pdf": bool(pdf_groups),
    }


@router.get("/courses/{course_id}/lesson-status")
def get_lesson_status(course_id: str):
    status = lesson_processor.get_status(course_id=course_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Aucun traitement de leçon pour ce cours.")

    return status


@router.patch("/courses/{course_id}/subject")
def assign_course_subject(course_id: str, request: CourseSubject):

    try:
        result = subject_manager.assign_course(
            course_id=course_id,
            subject=request.subject,
            lesson_number=request.lesson_number,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if result is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return result


@router.post("/subjects/{subject}/revision-plan")
def create_revision_plan(subject: str, request: RevisionPlanRequest, background_tasks: BackgroundTasks):

    try:
        plan = revision_planner.prepare(
            subject=subject,
            exam_date_text=request.exam_date,
            minutes_per_day=request.minutes_per_day,
            start_date_text=request.start_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if plan is None:
        raise HTTPException(status_code=404, detail="Matière introuvable.")

    background_tasks.add_task(revision_planner.process, plan_id=plan["plan_id"])

    return {"plan_id": plan["plan_id"], "subject": plan["subject"], "status": "processing"}


@router.get("/plans")
def list_revision_plans(subject: Optional[str] = None):
    return {"plans": revision_planner.list_plans(subject=subject)}


@router.get("/plans/{plan_id}")
def get_revision_plan_by_id(plan_id: str):
    plan = revision_planner.get_plan(plan_id=plan_id)

    if plan is None:
        raise HTTPException(status_code=404, detail="Plan introuvable.")

    return plan


@router.get("/plans/{plan_id}/export")
def export_revision_plan(plan_id: str, file_format: str = Query("pdf", alias="format")):

    try:
        exported = revision_planner.export(plan_id=plan_id, file_format=file_format or "pdf")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if exported is None:
        raise HTTPException(status_code=404, detail="Plan introuvable.")

    return Response(
        content=exported["data"],
        media_type=exported["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{exported["file_name"]}"'},
    )


@router.delete("/plans/{plan_id}")
def delete_revision_plan(plan_id: str):

    if not revision_planner.delete_plan(plan_id=plan_id):
        raise HTTPException(status_code=404, detail="Plan introuvable.")

    return {"plan_id": plan_id, "deleted": True}


@router.get("/revision-offers")
def list_revision_offers():
    return {"offers": revision_offers.list_offers()}


@router.post("/courses/{course_id}/events/{event_id}/revision")
def answer_revision_offer(course_id: str, event_id: str, answer: RevisionAnswer, background_tasks: BackgroundTasks):

    try:
        result = revision_offers.answer(
            course_id=course_id,
            event_id=event_id,
            accept=answer.accept,
            minutes_per_day=answer.minutes_per_day,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if result is None:
        raise HTTPException(status_code=404, detail="Cours ou événement introuvable.")

    if result["plan"] is None:
        return {"revision": result["revision"], "plan_id": None}

    background_tasks.add_task(revision_planner.process, plan_id=result["plan"]["plan_id"])

    return {"revision": result["revision"], "plan_id": result["plan"]["plan_id"], "status": "processing"}