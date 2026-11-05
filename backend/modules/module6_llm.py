from groq import Groq

from dotenv import load_dotenv
import os
import time

load_dotenv()



class LlmClient:
    def __init__(self):
        self.groq_client = None
        self.token_log = []
        self.tokens_per_minute = 7000


    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()


    @staticmethod
    def estimate_tokens(text):
        return len(text) // 3 + 1


    def get_groq_client(self):
        if self.groq_client is None:
            self.groq_client = Groq(api_key=os.environ["GROQ_KEY"])

        return self.groq_client


    def record_tokens(self, tokens):
        self.token_log.append((time.time(), tokens))


    def wait_for_budget(self, tokens):

        if tokens > self.tokens_per_minute:
            raise ValueError("Le texte est trop long pour être envoyé en une seule fois.")

        while True:
            now = time.time()
            self.token_log = [(moment, used) for (moment, used) in self.token_log if now - moment < 60]
            tokens_used = sum(used for (moment, used) in self.token_log)

            if tokens_used + tokens <= self.tokens_per_minute:
                return

            time.sleep(5)


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

        self.record_tokens(self.estimate_tokens(context + text_interaction + response))

        return response


    def ask_paced(self, context, text_interaction):

        needed_tokens = self.estimate_tokens(context + text_interaction) + 1500
        self.wait_for_budget(tokens=needed_tokens)

        for attempt in range(3):
            try:
                return self.ask(context=context, text_interaction=text_interaction)
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(20)


    def transcribe(self, audio_file_name, audio_bytes, language, prompt):

        transcription = self.get_groq_client().audio.transcriptions.create(
            file=(audio_file_name, audio_bytes),
            model="whisper-large-v3-turbo",
            language=language,
            prompt=prompt,
        )

        return transcription.text