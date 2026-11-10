from fastapi import FastAPI, HTTPException
from mistralai.client.errors import MistralError
from pydantic import BaseModel
from llm_agent import ConversationAgent
import base64


class ChatRequest(BaseModel):
    message: str
    voice: bool = True


class ChatResponse(BaseModel):
    reply: str
    audio: str | None = None


class TranscriptionRequest(BaseModel):
    audio: str
    file_name: str = "audio.m4a"


class TranscriptionResponse(BaseModel):
    text: str


class JarvisApi:
    def __init__(self):
        self.app = FastAPI(title="JARVIS")
        self.conversation_agent_object = ConversationAgent()

        self.app.add_api_route("/health", self.health, methods=["GET"])
        self.app.add_api_route("/chat", self.chat, methods=["POST"], response_model=ChatResponse)
        self.app.add_api_route("/transcribe", self.transcribe, methods=["POST"], response_model=TranscriptionResponse)

    def health(self):
        return {"status": "ok"}

    @staticmethod
    def mistral_error(error):
        print(f"[JARVIS] Erreur Mistral {error.status_code} : {error.body}", flush=True)
        if error.status_code == 429:
            return HTTPException(status_code=503, detail="Trop de demandes en même temps, réessaie dans quelques secondes.")
        return HTTPException(status_code=503, detail=f"JARVIS est momentanément indisponible (erreur Mistral {error.status_code}).")

    def chat(self, request: ChatRequest):
        try:
            reply = self.conversation_agent_object.ask_llm(request.message)
        except MistralError as error:
            raise self.mistral_error(error)

        audio = None
        if request.voice:
            try:
                audio = base64.b64encode(self.conversation_agent_object.text_to_speech(reply)).decode("utf-8")
            except MistralError as error:
                # Pas de voix Mistral : le téléphone lira la réponse avec sa propre voix.
                print(f"[JARVIS] Voix indisponible ({error.status_code}) : {error.body}", flush=True)

        return ChatResponse(reply=reply, audio=audio)

    def transcribe(self, request: TranscriptionRequest):
        try:
            # Le téléphone envoie l'enregistrement encodé en base64 : on le retransforme en octets.
            audio = base64.b64decode(request.audio)
        except ValueError:
            raise HTTPException(status_code=400, detail="L'enregistrement audio est illisible.")

        try:
            text = self.conversation_agent_object.transcribe(audio, file_name=request.file_name)
        except MistralError as error:
            raise self.mistral_error(error)
        return TranscriptionResponse(text=text)


jarvis_api_object = JarvisApi()
app = jarvis_api_object.app