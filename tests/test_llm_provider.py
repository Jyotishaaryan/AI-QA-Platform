import pytest

from app.core.config import get_settings
from app.services.llm import GroqProvider, build_provider


@pytest.mark.asyncio
async def test_groq_is_default_provider(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "test-key")

    provider = build_provider()
    assert isinstance(provider, GroqProvider)
    assert str(provider.client.base_url).rstrip("/") == "https://api.groq.com/openai/v1"
    await provider.aclose()
