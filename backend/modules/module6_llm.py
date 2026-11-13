from groq import Groq

from dotenv import load_dotenv
import os
import threading
import time

load_dotenv()



class LlmClient:
    def __init__(self):
        self.text_provider = os.environ.get("LLM_TEXT_PROVIDER", "mistral").lower()
        self.audio_provider = os.environ.get("LLM_AUDIO_PROVIDER", "mistral").lower()

        for provider in (self.text_provider, self.audio_provider):
            if provider not in ("mistral", "groq"):
                raise ValueError("Les fournisseurs possibles sont « mistral » et « groq ».")

        self.mistral_text_model = os.environ.get("MISTRAL_TEXT_MODEL", "mistral-small-latest")
        self.mistral_audio_model = "voxtral-mini-latest"
        self.groq_text_model = "openai/gpt-oss-120b"
        self.groq_audio_model = os.environ.get("GROQ_AUDIO_MODEL", "whisper-large-v3")

        self.groq_client = None
        self.mistral_client = None
        self.token_log = []
        self.tokens_per_minute = 200000 if self.text_provider == "mistral" else 7000

        self.mistral_interval = 1.1
        self.last_mistral_call = 0
        self.pace_lock = threading.Lock()


    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()


    @staticmethod
    def estimate_tokens(text):
        return len(text) // 3 + 1


    @staticmethod
    def extract_text(content):

        if isinstance(content, str):
            return content

        return "".join(chunk.text for chunk in content if getattr(chunk, "type", None) == "text")


    def get_groq_client(self):
        if self.groq_client is None:
            self.groq_client = Groq(api_key=os.environ["GROQ_KEY"])

        return self.groq_client


    def get_mistral_client(self):

        if self.mistral_client is None:
            try:
                from mistralai.client import Mistral
            except ImportError:
                from mistralai import Mistral

            try:
                self.mistral_client = Mistral(api_key=os.environ["MISTRAL_KEY"], timeout_ms=120000)
            except TypeError:
                self.mistral_client = Mistral(api_key=os.environ["MISTRAL_KEY"])

        return self.mistral_client


    def pace_mistral(self):

        with self.pace_lock:
            wait = self.mistral_interval - (time.time() - self.last_mistral_call)

            if wait > 0:
                time.sleep(wait)

            self.last_mistral_call = time.time()


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


    def complete(self, messages):

        if self.text_provider == "mistral":
            self.pace_mistral()

            response = self.get_mistral_client().chat.complete(
                model=self.mistral_text_model,
                messages=messages,
            )

            return self.extract_text(content=response.choices[0].message.content)

        return self.get_groq_client().chat.completions.create(
            messages=messages,
            model=self.groq_text_model,
            include_reasoning=False,
        ).choices[0].message.content


    def ask(self, context, text_interaction):

        response = self.complete(
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
        )

        self.record_tokens(self.estimate_tokens(context + text_interaction + response))

        return response


    def ask_with_history(self, context, history, text_interaction):

        messages = [{"role": "system", "content": context}] + history + [{"role": "user", "content": text_interaction}]

        response = self.complete(messages=messages)

        history_text = "".join(message["content"] for message in history)
        self.record_tokens(self.estimate_tokens(context + history_text + text_interaction + response))

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


    def transcribe(self, audio_file_name, audio_bytes, language, prompt, vocabulary=None):

        if self.audio_provider == "mistral":
            self.pace_mistral()

            options = {}

            if vocabulary:
                words = []

                for term in vocabulary:
                    for word in term.replace(",", " ").split():
                        if word.lower() not in [kept.lower() for kept in words]:
                            words.append(word)

                options["context_bias"] = words[:100]

            try:
                transcription = self.get_mistral_client().audio.transcriptions.complete(
                    model=self.mistral_audio_model,
                    file={"content": audio_bytes, "file_name": audio_file_name},
                    language=language,
                    **options,
                )
            except TypeError:
                transcription = self.get_mistral_client().audio.transcriptions.complete(
                    model=self.mistral_audio_model,
                    file={"content": audio_bytes, "file_name": audio_file_name},
                    language=language,
                )

            return transcription.text

        transcription = self.get_groq_client().audio.transcriptions.create(
            file=(audio_file_name, audio_bytes),
            model=self.groq_audio_model,
            language=language,
            prompt=prompt,
            temperature=0,
        )

        return transcription.text