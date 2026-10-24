from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "assistant-intelligent"
    environment: str = "development"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
_context_path = Path(__file__).with_name("context.txt")


def personality_context() -> str:
    return _context_path.read_text(encoding="utf-8").strip()


async def generate_reply(prompt: str) -> str:
    """Return a local response until a provider client is configured."""
    if not prompt.strip():
        raise ValueError("Le message ne peut pas être vide.")
    return (
        "Je peux vous aider. Aucun fournisseur LLM n'est configuré pour le moment. "
        "Votre demande a été reçue : "
        f"{prompt.strip()}"
    )
