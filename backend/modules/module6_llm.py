from groq import Groq

from dotenv import load_dotenv
import os

load_dotenv()



class LlmClient:
    def __init__(self):
        self.groq_client = None


    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()


    def get_groq_client(self):
        if self.groq_client is None:
            self.groq_client = Groq(api_key=os.environ["GROQ_KEY"])

        return self.groq_client


    def ask(self, context, text_interaction):

        response = self.get_groq_client().chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": context
                },
                {
                    "role": "user",
                    "content": text_interaction,
                }
            ],
            model="openai/gpt-oss-120b",
            include_reasoning=False,
        ).choices[0].message.content

        return response


    def transcribe(self, audio_file_name, audio_bytes, language):

        transcription = self.get_groq_client().audio.transcriptions.create(
            file=(audio_file_name, audio_bytes),
            model="whisper-large-v3-turbo",
            language=language,
        )

        return transcription.text