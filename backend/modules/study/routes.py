from datetime import date
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

from modules.study.audio_splitter import AudioSplitter
from modules.study.explainer import Explainer
from modules.study.exporter import StudyExporter
from modules.study.flashcards import FlashcardManager
from modules.study.lessons import LessonProcessor
from modules.study.library import StudyLibrary
from modules.study.long_audio import LongAudioProcessor
from modules.study.marks import CourseMarks
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
explainer = Explainer(study_service=study_service, subject_manager=subject_manager)
course_marks = CourseMarks(study_service=study_service)
flashcards = FlashcardManager(
    study_service=study_service,
    subject_manager=subject_manager,
    study_exporter=study_exporter,
)
study_library = StudyLibrary(
    study_service=study_service,
    subject_manager=subject_manager,
    revision_planner=revision_planner,
    study_exporter=study_exporter,
)



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



class FlashcardRequest(BaseModel):
    card_count: int = Field(default=10, ge=3, le=30)



class VocabularyRequest(BaseModel):
    terms: List[str]



class MarkRequest(BaseModel):
    text: str



class ExplainRequest(BaseModel):
    topic: str
    level: Literal["simple", "plus_simple", "approfondi"] = "simple"
    course_id: Optional[str] = None
    subject: Optional[str] = None



class ExplainCheck(BaseModel):
    topic: str
    question: str
    answer: str
    course_id: Optional[str] = None
    subject: Optional[str] = None



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
def summarize_course(course_id: str, redo: bool = False):

    try:
        summary = study_service.summarize_course(course_id=course_id, redo=redo)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service de résumé est indisponible, réessaie dans une minute.")

    if summary is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "summary": summary}


@router.post("/courses/{course_id}/summary/start")
def start_course_summary(course_id: str, background_tasks: BackgroundTasks, redo: bool = False):

    try:
        job = study_service.prepare_summary_job(course_id=course_id, redo=redo)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if job is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    background_tasks.add_task(study_service.process_summary_job, course_id=course_id)

    return {"course_id": course_id, **job}


@router.get("/courses/{course_id}/summary/status")
def get_course_summary_status(course_id: str):
    status = study_service.get_summary_status(course_id=course_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Aucun résumé en cours ou terminé pour ce cours.")

    return {"course_id": course_id, **status}


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

    study_library.record_correction(quiz_id=quiz_id, correction=correction)

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
    audio_1: Optional[UploadFile] = File(None),
    audio_2: Optional[UploadFile] = File(None),
    audio_3: Optional[UploadFile] = File(None),
    audio_4: Optional[UploadFile] = File(None),
    audio_5: Optional[UploadFile] = File(None),
    audio_6: Optional[UploadFile] = File(None),
    audio_7: Optional[UploadFile] = File(None),
    audio_8: Optional[UploadFile] = File(None),
    pdf_file: Optional[UploadFile] = File(None),
    user_consent: bool = Form(False),
    lesson_number: str = Form(""),
    vocabulary: str = Form(""),
):
    if lesson_number.strip() and not lesson_number.strip().isdigit():
        raise HTTPException(status_code=400, detail="Le numéro de la leçon doit être un nombre entier.")

    audio_slots = [audio_1, audio_2, audio_3, audio_4, audio_5, audio_6, audio_7, audio_8]
    audios = [(audio.filename, audio.file.read()) for audio in audio_slots if audio is not None and audio.filename]
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
        if audios:
            lesson_processor.check_audios(audios=audios, user_consent=user_consent)

        if pdf_bytes:
            pdf_groups = study_service.prepare_pdf(
                course_id=course_id,
                pdf_file_name=pdf_file.filename,
                pdf_bytes=pdf_bytes,
            )

        if vocabulary.strip():
            study_service.set_vocabulary(course_id=course_id, terms=vocabulary.split(","))
    except (PermissionError, ValueError) as error:
        study_service.delete_course(course_id=course_id)

        if isinstance(error, PermissionError):
            raise HTTPException(status_code=403, detail=str(error))

        raise HTTPException(status_code=400, detail=str(error))

    if audios or pdf_groups:
        lesson_processor.prepare(course_id=course_id, audio_count=len(audios))
        background_tasks.add_task(
            lesson_processor.process,
            course_id=course_id,
            audios=audios,
            pdf_groups=pdf_groups,
        )

    return {
        **lesson,
        "status": "processing" if (audios or pdf_groups) else "empty",
        "audio_count": len(audios),
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


@router.get("/library")
def get_library(subject: Optional[str] = None):
    return study_library.get_library(subject=subject)


@router.get("/library/quizzes")
def list_library_quizzes(subject: Optional[str] = None, course_id: Optional[str] = None):
    return {"quizzes": study_library.list_quizzes(subject=subject, course_id=course_id)}


@router.get("/library/quizzes/{quiz_id}")
def get_library_quiz(quiz_id: str):
    quiz = study_library.get_quiz(quiz_id=quiz_id)

    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz introuvable.")

    return quiz


@router.get("/library/quizzes/{quiz_id}/export")
def export_library_quiz(quiz_id: str, file_format: str = Query("pdf", alias="format")):

    try:
        exported = study_library.export_quiz(quiz_id=quiz_id, file_format=file_format or "pdf")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if exported is None:
        raise HTTPException(status_code=404, detail="Quiz introuvable.")

    return Response(
        content=exported["data"],
        media_type=exported["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{exported["file_name"]}"'},
    )


@router.delete("/library/quizzes/{quiz_id}")
def delete_library_quiz(quiz_id: str):

    if not study_library.delete_quiz(quiz_id=quiz_id):
        raise HTTPException(status_code=404, detail="Quiz introuvable.")

    return {"quiz_id": quiz_id, "deleted": True}


@router.post("/explain")
def explain_topic(request: ExplainRequest):

    try:
        result = explainer.explain(
            topic=request.topic,
            level=request.level,
            course_id=request.course_id or None,
            subject=request.subject or None,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible, réessaie dans une minute.")

    return result


@router.post("/explain/check")
def check_explanation(request: ExplainCheck):

    try:
        result = explainer.check(
            topic=request.topic,
            question=request.question,
            answer=request.answer,
            course_id=request.course_id or None,
            subject=request.subject or None,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible, réessaie dans une minute.")

    return result


@router.post("/courses/{course_id}/marks")
def add_course_mark(course_id: str, request: MarkRequest):

    try:
        mark = course_marks.add_mark(course_id=course_id, text=request.text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if mark is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return mark


@router.get("/courses/{course_id}/marks")
def list_course_marks(course_id: str):
    marks = course_marks.list_marks(course_id=course_id)

    if marks is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "marks": marks}


@router.delete("/courses/{course_id}/marks/{mark_id}")
def delete_course_mark(course_id: str, mark_id: str):
    deleted = course_marks.delete_mark(course_id=course_id, mark_id=mark_id)

    if deleted is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    if not deleted:
        raise HTTPException(status_code=404, detail="Passage marqué introuvable.")

    return {"course_id": course_id, "mark_id": mark_id, "deleted": True}


@router.get("/courses/{course_id}/marked-summary")
def get_marked_summary(course_id: str):

    try:
        result = course_marks.get_marked_summary(course_id=course_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if result is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return result


def make_download(exported):
    return Response(
        content=exported["data"],
        media_type=exported["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{exported["file_name"]}"'},
    )


@router.post("/courses/{course_id}/flashcards")
def create_flashcards(course_id: str, request: FlashcardRequest):

    try:
        deck = flashcards.generate(course_id=course_id, card_count=request.card_count)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Le service est indisponible ou les fiches sont invalides, réessaie dans une minute.")

    if deck is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return deck


@router.get("/courses/{course_id}/flashcards")
def get_flashcards(course_id: str):
    deck = flashcards.get_deck(course_id=course_id)

    if deck is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return deck


@router.get("/courses/{course_id}/flashcards/export")
def export_flashcards(course_id: str, file_format: str = Query("csv", alias="format")):

    try:
        exported = flashcards.export_course(course_id=course_id, file_format=file_format or "csv")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if exported is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return make_download(exported=exported)


@router.delete("/courses/{course_id}/flashcards/{card_id}")
def delete_flashcard(course_id: str, card_id: str):
    deleted = flashcards.delete_card(course_id=course_id, card_id=card_id)

    if deleted is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    if not deleted:
        raise HTTPException(status_code=404, detail="Fiche introuvable.")

    return {"course_id": course_id, "card_id": card_id, "deleted": True}


@router.delete("/courses/{course_id}/flashcards")
def delete_flashcards(course_id: str):
    count = flashcards.delete_deck(course_id=course_id)

    if count is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "deleted_cards": count}


@router.get("/subjects/{subject}/flashcards")
def get_subject_flashcards(subject: str):

    try:
        deck = flashcards.get_subject_deck(subject=subject)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if deck is None:
        raise HTTPException(status_code=404, detail="Matière introuvable.")

    return deck


@router.get("/subjects/{subject}/flashcards/export")
def export_subject_flashcards(subject: str, file_format: str = Query("csv", alias="format")):

    try:
        exported = flashcards.export_subject(subject=subject, file_format=file_format or "csv")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if exported is None:
        raise HTTPException(status_code=404, detail="Matière introuvable.")

    return make_download(exported=exported)


@router.put("/courses/{course_id}/vocabulary")
def set_course_vocabulary(course_id: str, request: VocabularyRequest):

    try:
        vocabulary = study_service.set_vocabulary(course_id=course_id, terms=request.terms)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if vocabulary is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "vocabulary": vocabulary}


@router.get("/courses/{course_id}/vocabulary")
def get_course_vocabulary(course_id: str):
    vocabulary = study_service.get_vocabulary(course_id=course_id)

    if vocabulary is None:
        raise HTTPException(status_code=404, detail="Cours introuvable.")

    return {"course_id": course_id, "vocabulary": vocabulary}