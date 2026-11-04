from modules.module6_llm import LlmClient

import os


class StudyService:
    def __init__(self):
        self.llm_client = LlmClient()
        self.context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_study.txt")
        )
        self.max_audio_size = 25 * 1024 * 1024
        self.default_prompt = "Transcription d'un cours en français."
        self.courses = {}


    def get_status(self):
        return {"module": "study", "status": "ok"}


    def ask_llm(self, text_interaction):
        return self.llm_client.ask(context=self.context, text_interaction=text_interaction)


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

        if course_id not in self.courses:
            self.courses[course_id] = {"transcript": "", "chunk_count": 0}

        course = self.courses[course_id]

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

        course["transcript"] = (course["transcript"] + " " + chunk_text).strip()
        course["chunk_count"] = chunk_index

        return {
            "course_id": course_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "chunk_count": course["chunk_count"],
        }


    def get_course_transcript(self, course_id):

        if course_id not in self.courses:
            return None

        return self.courses[course_id]