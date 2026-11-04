from modules.module6_llm import LlmClient

import os


class StudyService:
    def __init__(self):
        self.llm_client = LlmClient()
        self.context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_study.txt")
        )
        self.max_audio_size = 25 * 1024 * 1024


    def get_status(self):
        return {"module": "study", "status": "ok"}


    def ask_llm(self, text_interaction):
        return self.llm_client.ask(context=self.context, text_interaction=text_interaction)


    def transcribe_course(self, audio_file_name, audio_bytes, user_consent):

        if not user_consent:
            raise PermissionError("Autorisation refusee : je ne transcris pas sans ton accord.")

        if len(audio_bytes) == 0:
            raise ValueError("Le fichier audio est vide.")

        if len(audio_bytes) > self.max_audio_size:
            raise ValueError("Le fichier audio depasse 25 Mo : il faut le decouper.")

        transcript = self.llm_client.transcribe(
            audio_file_name=audio_file_name,
            audio_bytes=audio_bytes,
            language="fr",
        )

        return transcript