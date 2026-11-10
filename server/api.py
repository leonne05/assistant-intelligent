from fastapi import FastAPI, HTTPException
from mistralai.client.errors import MistralError
from pydantic import BaseModel
from llm_agent import ConversationAgent


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class JarvisApi:
    def __init__(self):
        self.app = FastAPI(title="JARVIS")
        self.conversation_agent_object = ConversationAgent()

        self.app.add_api_route("/health", self.health, methods=["GET"])
        self.app.add_api_route("/chat", self.chat, methods=["POST"], response_model=ChatResponse)

    def health(self):
        return {"status": "ok"}

    def chat(self, request: ChatRequest):
        try:
            reply = self.conversation_agent_object.ask_llm(request.message)
        except MistralError as error:
            print(f"[JARVIS] Erreur Mistral {error.status_code} : {error.body}")
            if error.status_code == 429:
                raise HTTPException(status_code=503, detail="Trop de demandes en même temps, réessaie dans quelques secondes.")
            raise HTTPException(status_code=503, detail="JARVIS est momentanément indisponible, réessaie dans un instant.")
        return ChatResponse(reply=reply)


jarvis_api_object = JarvisApi()
app = jarvis_api_object.app