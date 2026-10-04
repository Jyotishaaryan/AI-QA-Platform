from types import SimpleNamespace

import pytest

from app.services.chat import ChatService
from app.services.llm import LLMResult


class MockProvider:
    async def answer(self, question):
        assert question == "What is AI?"
        return LLMResult("AI answer", "mock-model", 4, 8, 12)


class FakeDB:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_chat_returns_usage_and_persists(monkeypatch):
    from app.services import chat

    monkeypatch.setattr(chat, "build_fallback_provider", lambda: None)
    service = ChatService(MockProvider())
    monkeypatch.setattr(service, "_limit", lambda user_id: _done())
    monkeypatch.setattr(service, "_cached", lambda question: _none())
    monkeypatch.setattr(service, "_save_cache", lambda question, result: _done())
    db = FakeDB()
    result, latency, request_id = await service.execute(
        "What is AI?", SimpleNamespace(id=7), db, "req-1"
    )
    assert result.total_tokens == 12 and latency >= 0 and request_id == "req-1"
    assert db.items[0].user_id == 7 and db.items[0].status == "success"


async def _done():
    return None


async def _none():
    return None
