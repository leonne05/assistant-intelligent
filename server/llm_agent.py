from mistralai.client import Mistral
from mistralai.client.utils import BackoffStrategy, RetryConfig
from dotenv import load_dotenv
from intent_router import IntentRouter
from modules.planning_module import PlanningModule
import base64
import os


class ConversationAgent:
    MODEL = "ministral-8b-latest"
    TRANSCRIPTION_MODEL = "voxtral-mini-latest"
    SPEECH_MODEL = "voxtral-mini-tts-latest"

    def __init__(self):
        load_dotenv(override=True)
        self.mistral_client = Mistral(
            api_key=os.environ["MISTRAL_API_KEY"],
            # En cas d'erreur 429 (trop de demandes), réessaie automatiquement pendant 20 secondes maximum.
            retry_config=RetryConfig("backoff", BackoffStrategy(1000, 8000, 2.0, 20000), True),
        )
        self.conversation_history = [
            {
                "role": "system",
                "content": self.read_file(file_path="./context.txt"),
            }
        ]
        self.intent_router_object = IntentRouter(self.mistral_client)
        self.modules = [
            PlanningModule(),
        ]
        self.voice_id = None

    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def get_conversation_history(self):
        return self.conversation_history[1:]

    def update_conversation_history(self, role, text_interaction):
        self.conversation_history.append(
            {
                "role": role,
                "content": text_interaction,
            }
        )

    def transcribe(self, audio_interaction, file_name="audio.m4a"):
        transcription = self.mistral_client.audio.transcriptions.complete(
            model=self.TRANSCRIPTION_MODEL,
            file={"file_name": file_name, "content": audio_interaction},
            language="fr",
        )
        return transcription.text.strip()

    def find_french_voice(self):
        voices = self.mistral_client.audio.voices.list(limit=50, type_="preset").items
        for voice in voices:
            if any(language.lower().startswith("fr") for language in voice.languages or []):
                return voice.id
        return voices[0].id if voices else None

    def text_to_speech(self, text_interaction):
        if self.voice_id is None:
            self.voice_id = self.find_french_voice()

        speech = self.mistral_client.audio.speech.complete(
            model=self.SPEECH_MODEL,
            input=text_interaction,
            voice_id=self.voice_id,
            response_format="mp3",
        )
        # Mistral renvoie l'audio déjà encodé en base64 : on le décode en octets MP3.
        return base64.b64decode(speech.audio_data)

    def find_module(self, intent):
        for module in self.modules:
            if intent in module.get_intents():
                return module
        return None

    def generate_response(self):
        return self.mistral_client.chat.complete(
            model=self.MODEL,
            messages=self.conversation_history,
        ).choices[0].message.content

    def route(self, intent, text_interaction):
        if intent["intent"] == "CHAT_LIBRE":
            return self.generate_response()

        module = self.find_module(intent["intent"])
        if module is None:
            return "J'ai bien compris ta demande, mais je ne sais pas encore le faire. Cette fonctionnalité arrive bientôt."

        response = module.handle(intent["intent"], intent["entities"], text_interaction)
        if module.demo:
            response = f"(Démo, données fictives) {response}"
        return response

    def ask_llm(self, text_interaction):
        intent = self.intent_router_object.analyse_intent(text_interaction)
        print(f"[JARVIS] Intention : {intent['intent']} ({intent['confidence']}) {intent['entities']}")

        self.update_conversation_history(role="user", text_interaction=text_interaction)

        try:
            response = self.route(intent, text_interaction)
        except Exception:
            # La question est restée sans réponse : on la retire de l'historique.
            self.conversation_history.pop()
            raise

        self.update_conversation_history(role="assistant", text_interaction=response)
        return response


if __name__ == "__main__":
    conversation_agent_object = ConversationAgent()
    print("Parle à JARVIS (laisse vide et appuie sur Entrée pour quitter).")
    while True:
        question = input("\nToi : ")
        if question == "":
            break
        print(f"JARVIS : {conversation_agent_object.ask_llm(question)}")