from modules.module6_llm import LlmClient

from pypdf import PdfReader
import io
import os


class StudyService:
    def __init__(self):
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
        self.max_audio_size = 25 * 1024 * 1024
        self.max_summaries_size = 20000
        self.max_pdf_bytes = 20 * 1024 * 1024
        self.max_pdf_chars = 60000
        self.pdf_group_size = 5000
        self.max_notes_size = 10000
        self.default_prompt = "Transcription d'un cours en français."
        self.courses = {}


    def get_status(self):
        return {"module": "study", "status": "ok"}


    def ask_llm(self, text_interaction):
        return self.llm_client.ask(context=self.context, text_interaction=text_interaction)


    def get_or_create_course(self, course_id):

        if course_id not in self.courses:
            self.courses[course_id] = {
                "transcript": "",
                "chunk_count": 0,
                "chunks": [],
                "chunk_summaries": [],
                "summary": None,
                "pdf": None,
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

        course["transcript"] = (course["transcript"] + " " + chunk_text).strip()
        course["chunks"].append(chunk_text)
        course["chunk_summaries"].append(chunk_summary)
        course["chunk_count"] = chunk_index

        return {
            "course_id": course_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "chunk_summary": chunk_summary,
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

        except Exception as error:
            pdf["status"] = "error"
            pdf["error"] = str(error)


    def get_pdf_status(self, course_id):

        if course_id not in self.courses:
            return None

        return self.courses[course_id]["pdf"]