import pytest
from fastapi.testclient import TestClient

import chatbot
import main

client = TestClient(main.app)
OPPORTUNITY = {
    "title": "Computer Science Fellowship",
    "organization": "Example Foundation",
    "deadline": "Unknown",
    "educationRequirements": "Verify on official portal",
    "officialUrl": "https://example.org/fellowship",
}


@pytest.fixture
def restore_search_function(monkeypatch):
    monkeypatch.setattr(chatbot, "_search_fn", None)


def test_chatbot_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CHATBOT_ENABLED", raising=False)
    assert chatbot.is_enabled() is False


def test_disabled_chatbot_has_config_and_404(monkeypatch, restore_search_function):
    monkeypatch.setenv("CHATBOT_ENABLED", "false")
    assert client.get("/api/chat-config").json() == {"enabled": False}
    assert client.post("/api/chat", json={"message": "fellowship"}).status_code == 404


def test_chatbot_without_gemini_returns_search_list(monkeypatch, restore_search_function):
    async def search_fn(**kwargs):
        assert kwargs == {
            "q": "fellowship",
            "category": None,
            "location": None,
            "work_mode": None,
            "education": None,
            "refresh": False,
        }
        return {"opportunities": [OPPORTUNITY]}

    chatbot.set_search_function(search_fn)
    monkeypatch.setenv("CHATBOT_ENABLED", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = client.post("/api/chat", json={"message": " fellowship "})

    assert response.status_code == 200
    assert "Computer Science Fellowship" in response.json()["reply"]
    assert "https://example.org/fellowship" in response.json()["reply"]


def test_chatbot_uses_available_model_and_bounds_history(monkeypatch, restore_search_function):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "Verify details on the official portal."}]}}
                ]
            }

    class FakeAsyncClient:
        request = None

        def __init__(self, timeout):
            assert timeout == 15.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers, json):
            FakeAsyncClient.request = {"url": url, "headers": headers, "json": json}
            return FakeResponse()

    async def search_fn(**kwargs):
        return {"opportunities": [OPPORTUNITY]}

    chatbot.set_search_function(search_fn)
    monkeypatch.setattr(chatbot.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setenv("CHATBOT_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-in-url")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    history = [
        {"role": "Student", "text": f"message {index}"}
        for index in range(8)
    ]
    response = client.post(
        "/api/chat",
        json={"message": "fellowship", "history": history},
    )

    request = FakeAsyncClient.request
    assert response.status_code == 200
    assert response.json()["reply"] == "Verify details on the official portal."
    assert request["url"].endswith("/models/gemini-flash-lite-latest:generateContent")
    assert "test-key-not-in-url" not in request["url"]
    assert request["headers"]["x-goog-api-key"] == "test-key-not-in-url"
    assert len(request["json"]["contents"]) == 7
    assert request["json"]["contents"][0]["parts"][0]["text"] == "message 2"
    assert request["json"]["generationConfig"] == {"maxOutputTokens": 256, "temperature": 0.2}


def test_malformed_gemini_response_uses_fallback(monkeypatch, restore_search_function):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"unexpected": "shape"}

    class FakeAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    async def search_fn(**kwargs):
        return {"opportunities": [OPPORTUNITY]}

    chatbot.set_search_function(search_fn)
    monkeypatch.setattr(chatbot.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setenv("CHATBOT_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response = client.post("/api/chat", json={"message": "fellowship"})

    assert response.status_code == 200
    assert "Computer Science Fellowship" in response.json()["reply"]
