from modules.module6_llm import LlmClient
from modules.study.study_memory import StudyMemory

from pypdf import PdfReader
from datetime import date, datetime, timedelta
import io
import json
import os
import random
import re
import unicodedata
import uuid


class StudyService:
    def __init__(self, database_path=None):
        self.llm_client = LlmClient()
        self.context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_study.txt")
        )
        self.chunk_summary_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_chunk_summary.txt")
        )
        self.course_summary_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_course_summary.txt")
        )
        self.pdf_summary_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_pdf_summary.txt")
        )
        self.global_summary_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_global_summary.txt")
        )
        self.events_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_events.txt")
        )
        self.quiz_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_quiz.txt")
        )
        self.event_words = [
            "devoir", "examen", "partiel", "contrôle", "controle", "interro", "rendu", "rendre",
            "remettre", "projet", "soutenance", "qcm", "date limite", "avant le", "pour le",
            "dossier", "évaluation", "evaluation", "rattrapage", "exposé", "tp noté",
        ]
        self.date_words = [
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
            "janvier", "février", "fevrier", "mars", "avril", "mai", "juin", "juillet",
            "août", "aout", "septembre", "octobre", "novembre", "décembre", "decembre",
            "demain", "prochain", "semaine",
        ]
        self.week_days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        self.months = [
            "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
            "août", "septembre", "octobre", "novembre", "décembre",
        ]
        self.stop_words = [
            "les", "des", "une", "est", "que", "qui", "quoi", "dans", "pour", "avec", "sur", "par",
            "pas", "plus", "mais", "nous", "vous", "tout", "tous", "cette", "ces", "comme", "etait",
            "avait", "avais", "aussi", "fait", "faire", "peux", "peut", "dit", "dire", "parle",
            "parler", "cours", "prof", "professeur", "quel", "quelle", "quels", "quelles", "sont",
            "son", "ses", "ton", "tes", "mon", "mes", "aux", "ete", "etre", "avoir", "ainsi",
            "alors", "donc", "puis", "chose", "rappelle", "explique", "dis", "moi", "toi",
            "donne", "donner", "exemple", "exemples", "encore", "autre", "autres",
        ]
        self.answer_reminder = (
            "## Rappel avant de répondre\n"
            "- Réponds en 150 mots maximum, sauf si l'étudiant demande plus de détails.\n"
            "- Écris les formules en texte simple, par exemple : f'(x) = 2x ou (x+h)^2. "
            "Aucun code LaTeX : rien qui commence par une barre oblique inverse.\n"
            "- Si un extrait contient un exemple ou une explication du cours, utilise-le en priorité.\n"
            "- Si aucun extrait ne répond, dis-le en une phrase, puis donne au plus une courte explication générale. "
            "Ne dis jamais ce que le professeur a dit ou insiste à dire si ce n'est pas dans un extrait."
        )
        self.history_size = 10
        self.max_history_chars = 6000
        self.max_note_results = 3
        self.passage_size = 800
        self.weak_rate = 0.5
        self.strong_rate = 0.8
        self.max_quiz_chars = 9000
        self.min_quiz_chars = 200
        self.max_audio_size = 25 * 1024 * 1024
        self.max_summaries_size = 20000
        self.max_pdf_bytes = 20 * 1024 * 1024
        self.max_pdf_chars = 60000
        self.pdf_group_size = 5000
        self.max_notes_size = 10000
        self.default_prompt = "Transcription d'un cours en français."

        if database_path is None:
            database_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "data", "study.db")
            )

        self.memory = StudyMemory(database_path=database_path)
        self.courses = self.memory.load_all_courses()

        for course_id, course in self.courses.items():
            pdf = course["pdf"]

            if pdf is not None and pdf["status"] == "processing":
                pdf["status"] = "error"
                pdf["error"] = "Traitement interrompu par un redémarrage du serveur : renvoie le PDF."
                self.save_course(course_id=course_id)


    def get_status(self):
        return {"module": "study", "status": "ok"}


    def ask_llm(self, text_interaction):

        history = self.get_history_for_prompt()

        previous_question = None
        for message in reversed(history):
            if message["role"] == "user":
                previous_question = message["content"]
                break

        notes = self.search_notes(question=text_interaction, previous_question=previous_question)
        context = self.context + "\n\n" + self.format_notes(notes=notes) + "\n\n" + self.answer_reminder

        response = self.llm_client.ask_with_history(
            context=context,
            history=history,
            text_interaction=text_interaction,
        )

        self.memory.add_message(role="user", content=text_interaction)
        self.memory.add_message(role="assistant", content=response)

        sources = [note["label"] for note in notes]

        return {"response": response, "sources": sources}


    def get_history_for_prompt(self):

        messages = self.memory.get_recent_messages(limit=self.history_size)
        history = []
        total_chars = 0

        for message in reversed(messages):
            total_chars += len(message["content"])

            if total_chars > self.max_history_chars:
                break

            history.insert(0, {"role": message["role"], "content": message["content"]})

        return history


    def get_history(self, limit):
        return self.memory.get_recent_messages(limit=limit)


    def clear_history(self):
        self.memory.clear_messages()


    def normalize_text(self, text):
        text = unicodedata.normalize("NFD", text.lower())
        return "".join(char for char in text if unicodedata.category(char) != "Mn")


    def get_words(self, text):
        return re.findall(r"[a-z0-9]{3,}", self.normalize_text(text))


    def get_keywords(self, question):
        return {word[:5] for word in self.get_words(question) if word not in self.stop_words}


    def split_passages(self, text):

        pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
        passages = []
        current_passage = ""

        for piece in pieces:
            if not piece.strip():
                continue

            if current_passage and len(current_passage) + len(piece) + 1 > self.passage_size:
                passages.append(current_passage)
                current_passage = ""

            current_passage = (current_passage + " " + piece).strip()

        if current_passage:
            passages.append(current_passage)

        return passages


    def get_course_notes(self, course_id, course):

        notes = []

        for index, chunk_text in enumerate(course["chunks"]):
            for passage in self.split_passages(text=chunk_text):
                notes.append({
                    "label": f"cours {course_id}, ce que le prof a dit (morceau {index + 1})",
                    "content": passage,
                })

        if course["summary"]:
            for passage in self.split_passages(text=course["summary"]):
                notes.append({"label": f"cours {course_id}, résumé du cours", "content": passage})

        if course["pdf"] is not None and course["pdf"]["summary"]:
            for passage in self.split_passages(text=course["pdf"]["summary"]):
                notes.append({"label": f"cours {course_id}, résumé du PDF fusionné", "content": passage})

        return notes


    def search_notes(self, question, previous_question=None):

        keywords = self.get_keywords(question=question)

        if not keywords and previous_question:
            keywords = self.get_keywords(question=previous_question)

        return self.find_notes(keywords=keywords)


    def find_notes(self, keywords):

        if not keywords:
            return []

        needed_matches = 1 if len(keywords) == 1 else 2
        scored_notes = []

        for course_id, course in self.courses.items():
            for note in self.get_course_notes(course_id=course_id, course=course):
                note_stems = [word[:5] for word in self.get_words(note["content"])]
                matches = [stem for stem in note_stems if stem in keywords]

                if len(set(matches)) < needed_matches:
                    continue

                score = len(set(matches)) * 5 + len(matches)
                scored_notes.append((score, note))

        scored_notes.sort(key=lambda scored_note: scored_note[0], reverse=True)

        return [note for score, note in scored_notes[:self.max_note_results]]


    def format_notes(self, notes):

        if not notes:
            return "## Extraits de tes cours\n\n(Aucun extrait trouvé pour cette question.)"

        lines = ["## Extraits de tes cours", ""]

        for note in notes:
            lines.append(f"[{note['label']}]")
            lines.append(note["content"][:1200])
            lines.append("")

        return "\n".join(lines)


    def save_course(self, course_id):

        if course_id in self.courses:
            self.memory.save_course(course_id=course_id, course=self.courses[course_id])


    def delete_course(self, course_id):

        if course_id not in self.courses:
            return False

        del self.courses[course_id]
        self.memory.delete_course(course_id=course_id)
        self.memory.delete_quizzes(course_id=course_id)
        self.memory.delete_attempts(course_id=course_id)

        return True


    def list_courses(self):

        return [
            {
                "course_id": course_id,
                "chunk_count": course["chunk_count"],
                "has_summary": course["summary"] is not None,
                "has_pdf": course["pdf"] is not None,
                "pending_events": sum(1 for event in course["events"] if event["status"] == "pending"),
            }
            for course_id, course in self.courses.items()
        ]


    def get_or_create_course(self, course_id):

        if course_id not in self.courses:
            self.courses[course_id] = {
                "transcript": "",
                "chunk_count": 0,
                "chunks": [],
                "chunk_summaries": [],
                "summary": None,
                "pdf": None,
                "events": [],
            }

        return self.courses[course_id]


    def check_audio(self, audio_bytes, user_consent):

        if not user_consent:
            raise PermissionError("Autorisation refusée : je ne transcris pas sans ton accord.")

        if len(audio_bytes) == 0:
            raise ValueError("Le fichier audio est vide.")

        if len(audio_bytes) > self.max_audio_size:
            raise ValueError("Le fichier audio dépasse 25 Mo : il faut le découper.")


    def transcribe_course(self, audio_file_name, audio_bytes, user_consent):

        self.check_audio(audio_bytes=audio_bytes, user_consent=user_consent)

        transcript = self.llm_client.transcribe(
            audio_file_name=audio_file_name,
            audio_bytes=audio_bytes,
            language="fr",
            prompt=self.default_prompt,
        )

        return transcript


    def transcribe_chunk(self, course_id, chunk_index, audio_file_name, audio_bytes, user_consent):

        self.check_audio(audio_bytes=audio_bytes, user_consent=user_consent)

        course = self.get_or_create_course(course_id=course_id)

        expected_index = course["chunk_count"] + 1
        if chunk_index != expected_index:
            raise ValueError(f"Morceau attendu : {expected_index}, reçu : {chunk_index}.")

        previous_text_end = course["transcript"][-400:]

        chunk_text = self.llm_client.transcribe(
            audio_file_name=audio_file_name,
            audio_bytes=audio_bytes,
            language="fr",
            prompt=previous_text_end or self.default_prompt,
        )

        try:
            chunk_summary = self.summarize_chunk(chunk_text=chunk_text)
        except Exception:
            chunk_summary = None

        try:
            new_events = self.detect_events(course=course, chunk_text=chunk_text, chunk_index=chunk_index)
        except Exception:
            new_events = []

        course["transcript"] = (course["transcript"] + " " + chunk_text).strip()
        course["chunks"].append(chunk_text)
        course["chunk_summaries"].append(chunk_summary)
        course["chunk_count"] = chunk_index

        self.save_course(course_id=course_id)

        return {
            "course_id": course_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "chunk_summary": chunk_summary,
            "new_events": new_events,
            "chunk_count": course["chunk_count"],
        }


    def summarize_chunk(self, chunk_text):

        if not chunk_text.strip():
            return None

        return self.llm_client.ask(context=self.chunk_summary_context, text_interaction=chunk_text)


    def get_course_transcript(self, course_id):

        if course_id not in self.courses:
            return None

        return self.courses[course_id]


    def summarize_course(self, course_id, paced=False):

        if course_id not in self.courses:
            return None

        course = self.courses[course_id]

        if course["chunk_count"] == 0:
            raise ValueError("Ce cours n'a pas encore de texte.")

        chunk_summaries = []

        for index, chunk_text in enumerate(course["chunks"]):
            chunk_summary = course["chunk_summaries"][index]

            if chunk_summary is None:
                chunk_summary = self.summarize_chunk(chunk_text=chunk_text)
                course["chunk_summaries"][index] = chunk_summary

            if chunk_summary is not None:
                chunk_summaries.append(chunk_summary)

        if not chunk_summaries:
            raise ValueError("Il n'y a rien à résumer dans ce cours.")

        all_summaries = "\n\n".join(chunk_summaries)

        if len(all_summaries) > self.max_summaries_size:
            raise ValueError("Ce cours est trop long pour un résumé en une fois.")

        ask = self.llm_client.ask_paced if paced else self.llm_client.ask

        summary = ask(
            context=self.course_summary_context,
            text_interaction=all_summaries,
        )

        course["summary"] = summary

        self.save_course(course_id=course_id)

        return summary


    def extract_pdf_text(self, pdf_bytes):

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception:
            raise ValueError("Impossible de lire ce PDF (fichier abîmé ou protégé).")

        text = ""

        for page_number, page_text in enumerate(pages, start=1):
            if page_text.strip():
                text += f"[Page {page_number}]\n{page_text.strip()}\n\n"

        if len(text) < 200:
            raise ValueError("Ce PDF ne contient presque pas de texte (PDF scanné ?).")

        if len(text) > self.max_pdf_chars:
            raise ValueError("Ce PDF est trop long : il dépasse environ 60 000 caractères.")

        return text


    def split_pdf_text(self, text):

        pdf_groups = []
        current_group = ""

        for line in text.split("\n"):
            for start in range(0, max(len(line), 1), self.pdf_group_size):
                piece = line[start:start + self.pdf_group_size]

                if current_group and len(current_group) + len(piece) + 1 > self.pdf_group_size:
                    pdf_groups.append(current_group)
                    current_group = ""

                current_group += piece + "\n"

        if current_group.strip():
            pdf_groups.append(current_group)

        return pdf_groups


    def prepare_pdf(self, course_id, pdf_file_name, pdf_bytes):

        if len(pdf_bytes) == 0:
            raise ValueError("Le fichier PDF est vide.")

        if len(pdf_bytes) > self.max_pdf_bytes:
            raise ValueError("Le PDF dépasse 20 Mo.")

        course = self.get_or_create_course(course_id=course_id)

        if course["pdf"] is not None and course["pdf"]["status"] == "processing":
            raise ValueError("Un PDF est déjà en cours de traitement pour ce cours.")

        text = self.extract_pdf_text(pdf_bytes=pdf_bytes)
        pdf_groups = self.split_pdf_text(text=text)

        course["pdf"] = {
            "file_name": pdf_file_name,
            "status": "processing",
            "done_groups": 0,
            "group_count": len(pdf_groups),
            "summary": None,
            "error": None,
        }

        self.save_course(course_id=course_id)

        return pdf_groups


    def process_pdf(self, course_id, pdf_groups):

        course = self.courses[course_id]
        pdf = course["pdf"]

        try:
            notes = []

            for index, pdf_group in enumerate(pdf_groups):
                note = self.llm_client.ask_paced(
                    context=self.pdf_summary_context,
                    text_interaction=pdf_group,
                )
                notes.append(note)
                pdf["done_groups"] = index + 1
                self.save_course(course_id=course_id)

            all_notes = "\n\n".join(notes)

            if len(all_notes) > self.max_notes_size:
                raise ValueError("Les notes du PDF sont trop longues pour être fusionnées.")

            oral_summary = course["summary"]

            if oral_summary is None and course["chunk_count"] > 0:
                try:
                    oral_summary = self.summarize_course(course_id=course_id, paced=True)
                except ValueError:
                    oral_summary = None

            if oral_summary is None:
                oral_summary = "(Aucune explication orale n'est disponible pour ce cours.)"

            text_interaction = (
                "## NOTES DU PDF\n\n" + all_notes
                + "\n\n## CE QUE LE PROFESSEUR A DIT À L'ORAL\n\n" + oral_summary
            )

            pdf["summary"] = self.llm_client.ask_paced(
                context=self.global_summary_context,
                text_interaction=text_interaction,
            )
            pdf["status"] = "done"
            self.save_course(course_id=course_id)

        except Exception as error:
            pdf["status"] = "error"
            pdf["error"] = str(error)
            self.save_course(course_id=course_id)


    def get_pdf_status(self, course_id):

        if course_id not in self.courses:
            return None

        return self.courses[course_id]["pdf"]


    def has_event_hint(self, text):

        lower_text = text.lower()

        has_event_word = any(word in lower_text for word in self.event_words)
        has_date_word = any(word in lower_text for word in self.date_words) or any(char.isdigit() for char in lower_text)

        return has_event_word and has_date_word


    def get_calendar_text(self):

        today = date.today()

        lines = [f"Date du jour : {self.format_date(today)} ({today.isoformat()})", "", "Calendrier :"]

        for day_number in range(1, 22):
            day = today + timedelta(days=day_number)
            lines.append(f"- {self.format_date(day)} ({day.isoformat()})")

        return "\n".join(lines)


    def format_date(self, day):
        return f"{self.week_days[day.weekday()]} {day.day} {self.months[day.month - 1]} {day.year}"


    def parse_events(self, answer):

        start = answer.find("[")
        end = answer.rfind("]")

        if start == -1 or end == -1:
            return []

        try:
            raw_events = json.loads(answer[start:end + 1])
        except ValueError:
            return []

        today = date.today()
        events = []

        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                continue

            try:
                event_date = datetime.strptime(str(raw_event.get("date")), "%Y-%m-%d").date()
            except ValueError:
                continue

            if event_date < today:
                continue

            event_time = raw_event.get("time")
            if not isinstance(event_time, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", event_time):
                event_time = None

            event_type = raw_event.get("type")
            if event_type not in ("devoir", "examen", "autre"):
                event_type = "autre"

            events.append({
                "type": event_type,
                "title": str(raw_event.get("title") or "Échéance")[:120],
                "date": event_date.isoformat(),
                "time": event_time,
                "source_sentence": str(raw_event.get("source_sentence") or "")[:300],
            })

        return events


    def detect_events(self, course, chunk_text, chunk_index, paced=False):

        if not self.has_event_hint(chunk_text):
            return []

        ask = self.llm_client.ask_paced if paced else self.llm_client.ask

        answer = ask(
            context=self.events_context,
            text_interaction=self.get_calendar_text() + "\n\nExtrait du cours :\n" + chunk_text,
        )

        new_events = []

        for event in self.parse_events(answer=answer):
            already_known = any(
                known["type"] == event["type"] and known["date"] == event["date"] and known["time"] == event["time"]
                for known in course["events"]
            )

            if already_known:
                continue

            event["id"] = uuid.uuid4().hex[:8]
            event["status"] = "pending"
            event["chunk_index"] = chunk_index

            course["events"].append(event)
            new_events.append(event)

        return new_events


    def detect_course_events(self, course_id):

        if course_id not in self.courses:
            return None

        course = self.courses[course_id]
        new_events = []

        for index, chunk_text in enumerate(course["chunks"]):
            new_events += self.detect_events(
                course=course,
                chunk_text=chunk_text,
                chunk_index=index + 1,
                paced=True,
            )

        self.save_course(course_id=course_id)

        return new_events


    def get_events(self, course_id):

        if course_id not in self.courses:
            return None

        return self.courses[course_id]["events"]


    def decide_event(self, course_id, event_id, status):

        if course_id not in self.courses:
            return None

        for event in self.courses[course_id]["events"]:
            if event["id"] == event_id:

                if event["status"] != "pending":
                    raise ValueError("Cet événement a déjà été traité.")

                event["status"] = status
                self.save_course(course_id=course_id)
                return event

        return None


    def get_quiz_material(self, course):

        if course["pdf"] is not None and course["pdf"]["summary"]:
            material = course["pdf"]["summary"]
        elif course["summary"]:
            material = course["summary"]
        else:
            chunk_summaries = [summary for summary in course["chunk_summaries"] if summary]
            material = "\n\n".join(chunk_summaries) if chunk_summaries else course["transcript"]

        return material[:self.max_quiz_chars]


    def parse_quiz(self, answer):

        start = answer.find("[")
        end = answer.rfind("]")

        if start == -1 or end == -1:
            return []

        try:
            raw_questions = json.loads(answer[start:end + 1])
        except ValueError:
            return []

        questions = []

        for raw_question in raw_questions:
            if not isinstance(raw_question, dict):
                continue

            question_text = raw_question.get("question")
            choices = raw_question.get("choices")
            answer_index = raw_question.get("answer")

            if not isinstance(question_text, str) or not question_text.strip():
                continue

            if not isinstance(choices, list) or len(choices) != 4 or not all(isinstance(choice, str) and choice.strip() for choice in choices):
                continue

            if len(set(choice.strip().lower() for choice in choices)) != 4:
                continue

            if not isinstance(answer_index, int) or isinstance(answer_index, bool) or not 0 <= answer_index <= 3:
                continue

            correct_choice = choices[answer_index]
            shuffled_choices = list(choices)
            random.shuffle(shuffled_choices)

            questions.append({
                "question": question_text.strip(),
                "choices": shuffled_choices,
                "answer": shuffled_choices.index(correct_choice),
                "explanation": str(raw_question.get("explanation") or "")[:400],
                "topic": str(raw_question.get("topic") or "général")[:60],
            })

        return questions


    def generate_quiz(self, course_id, question_count):

        if course_id not in self.courses:
            return None

        course = self.courses[course_id]
        material = self.get_quiz_material(course=course)

        if len(material.strip()) < self.min_quiz_chars:
            raise ValueError("Ce cours n'a pas encore assez de contenu pour faire un quiz.")

        answer = self.llm_client.ask_paced(
            context=self.quiz_context,
            text_interaction=f"Nombre de questions demandé : {question_count}\n\nContenu du cours :\n{material}",
        )

        questions = self.parse_quiz(answer=answer)[:question_count]

        if not questions:
            raise RuntimeError("Le quiz généré est inutilisable, réessaie.")

        quiz_id = uuid.uuid4().hex[:8]
        quiz = {"quiz_id": quiz_id, "course_id": course_id, "questions": questions}

        self.memory.save_quiz(quiz_id=quiz_id, course_id=course_id, quiz=quiz)

        return self.get_public_quiz(quiz=quiz)


    def get_public_quiz(self, quiz):

        return {
            "quiz_id": quiz["quiz_id"],
            "course_id": quiz["course_id"],
            "question_count": len(quiz["questions"]),
            "questions": [
                {"number": number, "question": question["question"], "choices": question["choices"]}
                for number, question in enumerate(quiz["questions"], start=1)
            ],
        }


    def get_quiz(self, quiz_id):

        quiz = self.memory.load_quiz(quiz_id=quiz_id)

        if quiz is None:
            return None

        return self.get_public_quiz(quiz=quiz)


    def correct_quiz(self, quiz_id, answers):

        quiz = self.memory.load_quiz(quiz_id=quiz_id)

        if quiz is None:
            return None

        if quiz.get("corrected"):
            raise ValueError("Ce quiz a déjà été corrigé : génère-en un nouveau pour t'entraîner encore.")

        questions = quiz["questions"]

        if len(answers) != len(questions):
            raise ValueError(
                f"Ce quiz a {len(questions)} questions : envoie {len(questions)} réponses (null pour une question sautée)."
            )

        for answer in answers:
            if answer is not None and (isinstance(answer, bool) or not 0 <= answer <= 3):
                raise ValueError("Chaque réponse doit être un nombre de 0 à 3 (position du choix), ou null.")

        results = []
        attempts = []

        for number, (question, answer) in enumerate(zip(questions, answers), start=1):
            is_correct = answer == question["answer"]
            topic = question["topic"].strip().lower() or "général"

            results.append({
                "number": number,
                "question": question["question"],
                "your_answer": question["choices"][answer] if answer is not None else None,
                "correct_answer": question["choices"][question["answer"]],
                "is_correct": is_correct,
                "explanation": question["explanation"],
                "topic": topic,
            })
            attempts.append((topic, is_correct))

        self.memory.save_attempts(quiz_id=quiz_id, course_id=quiz["course_id"], results=attempts)

        quiz["corrected"] = True
        self.memory.save_quiz(quiz_id=quiz_id, course_id=quiz["course_id"], quiz=quiz)

        score = sum(1 for result in results if result["is_correct"])
        to_review = []

        for result in results:
            if not result["is_correct"] and result["topic"] not in to_review:
                to_review.append(result["topic"])

        return {
            "quiz_id": quiz_id,
            "course_id": quiz["course_id"],
            "score": score,
            "total": len(results),
            "score_percent": round(score * 100 / len(results)),
            "to_review": to_review,
            "results": results,
        }


    def get_gaps(self, course_id=None):

        stats = {}

        for row_course_id, topic, correct, answered_at in self.memory.get_attempts(course_id=course_id):
            key = (row_course_id, topic)

            if key not in stats:
                stats[key] = {
                    "course_id": row_course_id,
                    "topic": topic,
                    "attempts": 0,
                    "correct": 0,
                    "last_answered": answered_at,
                }

            stats[key]["attempts"] += 1
            stats[key]["correct"] += correct
            stats[key]["last_answered"] = max(stats[key]["last_answered"], answered_at)

        gaps = []

        for stat in stats.values():
            rate = stat["correct"] / stat["attempts"]
            stat["success_percent"] = round(rate * 100)

            if rate < self.weak_rate:
                stat["level"] = "a_retravailler"
            elif rate < self.strong_rate:
                stat["level"] = "moyen"
            else:
                stat["level"] = "acquis"

            gaps.append(stat)

        gaps.sort(key=lambda gap: (gap["success_percent"], -gap["attempts"]))

        return gaps


    def clear_gaps(self):
        self.memory.clear_attempts()