from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from google import genai
from groq import Groq
from mistralai import Mistral


Message = dict[str, str]
ProviderCall = Callable[[list[Message]], str]


class ConversationAgent:
    def __init__(self) -> None:
        load_dotenv()
        self.conversation_history: list[Message] = [
            {
                "role": "system",
                "content": self.read_file(
                    file_path=Path(__file__).with_name("context.txt")
                ),
            }
        ]
        self.providers: dict[str, ProviderCall] = {}
        self._configure_providers()
        self.provider_order = self._configured_provider_order()
        if not self.provider_order:
            raise RuntimeError(
                "Configurez au moins une clé parmi GROQ_KEY, GEMINI_API_KEY "
                "et MISTRAL_API_KEY."
            )

    @staticmethod
    def read_file(file_path: str | Path) -> str:
        return Path(file_path).read_text(encoding="utf-8")

    def get_conversation_history(self) -> list[Message]:
        return self.conversation_history[1:]

    def update_conversation_history(self, role: str, content: str) -> None:
        self.conversation_history.append({"role": role, "content": content})

    def ask_llm(self, text_interaction: str) -> str:
        if not text_interaction.strip():
            raise ValueError("Le message ne peut pas être vide.")

        self.update_conversation_history(role="user", content=text_interaction)
        errors: list[str] = []
        for provider_name in self.provider_order:
            try:
                response = self.providers[provider_name](self.conversation_history)
                if not response:
                    raise RuntimeError("Réponse vide.")
                self.update_conversation_history(role="assistant", content=response)
                return response
            except Exception as error:
                errors.append(f"{provider_name}: {error}")

        self.conversation_history.pop()
        raise RuntimeError(
            "Tous les fournisseurs LLM ont échoué : " + " | ".join(errors)
        )

    def _configure_providers(self) -> None:
        groq_key = os.environ.get("GROQ_KEY")
        if groq_key:
            groq_client = Groq(api_key=groq_key)
            groq_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
            self.providers["groq"] = lambda messages: (
                groq_client.chat.completions.create(
                    messages=messages,
                    model=groq_model,
                    include_reasoning=False,
                ).choices[0].message.content
                or ""
            )

        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            gemini_client = genai.Client(api_key=gemini_key)
            gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
            self.providers["gemini"] = lambda messages: (
                gemini_client.models.generate_content(
                    model=gemini_model,
                    contents=self._gemini_prompt(messages),
                ).text
                or ""
            )

        mistral_key = os.environ.get("MISTRAL_API_KEY")
        if mistral_key:
            mistral_client = Mistral(api_key=mistral_key)
            mistral_model = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
            self.providers["mistral"] = lambda messages: (
                mistral_client.chat.complete(
                    model=mistral_model,
                    messages=messages,
                ).choices[0].message.content
                or ""
            )

    def _configured_provider_order(self) -> list[str]:
        configured = set(self.providers)
        requested = os.environ.get(
            "LLM_PROVIDER_ORDER", "groq,gemini,mistral"
        ).split(",")
        return [
            provider.strip().casefold()
            for provider in requested
            if provider.strip().casefold() in configured
        ]

    @staticmethod
    def _gemini_prompt(messages: list[Message]) -> str:
        return "\n".join(
            f"{message['role']}: {message['content']}" for message in messages
        )


_conversation_agent: ConversationAgent | None = None


def get_conversation_agent() -> ConversationAgent:
    global _conversation_agent
    if _conversation_agent is None:
        _conversation_agent = ConversationAgent()
    return _conversation_agent


async def generate_reply(prompt: str) -> str:
    return get_conversation_agent().ask_llm(prompt)
