from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from actions import ActionStatus, PendingAction, create_action, list_actions, update_action
from llm import generate_reply
from memory import memory
from router import Intent, detect_intent


app = FastAPI(title="Assistant Intelligent", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class ChatResponse(BaseModel):
    reply: str
    intent: Intent


class ActionDecision(BaseModel):
    status: ActionStatus


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    intent = detect_intent(request.message)
    memory.add("user", request.message)

    if intent is Intent.ACTION:
        action = create_action(request.message)
        reply = f"Action mise en attente de validation : {action.id}"
    else:
        reply = await generate_reply(request.message)

    memory.add("assistant", reply)
    return ChatResponse(reply=reply, intent=intent)


@app.get("/actions", response_model=list[PendingAction])
async def get_actions() -> list[PendingAction]:
    return list_actions()


@app.patch("/actions/{action_id}", response_model=PendingAction)
async def decide_action(action_id: str, decision: ActionDecision) -> PendingAction:
    action = update_action(action_id, decision.status)
    if action is None:
        raise HTTPException(status_code=404, detail="Action introuvable ou déjà traitée.")
    return action


@app.post("/voice")
async def voice() -> dict[str, str]:
    raise HTTPException(
        status_code=501,
        detail="La transcription vocale n'est pas encore configurée.",
    )
