from modules.module6_llm import LlmClient

import os


class StudyService:
    def __init__(self):
        self.llm_client = LlmClient()
        self.context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_study.txt")
        )


    def get_status(self):
        return {"module": "study", "status": "ok"}


    def ask_llm(self, text_interaction):
        return self.llm_client.ask(context=self.context, text_interaction=text_interaction)