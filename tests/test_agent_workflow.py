import asyncio

from fastapi.testclient import TestClient

import main
from agent_workflow import AgentWorkflowRequest, run_agent_workflow

client = TestClient(main.app)

PROFILE = {
    "educationLevel": "Undergraduate",
    "fieldOfStudy": "Computer Science",
    "skills": ["Python", "Web Development"],
    "experienceLevel": "Beginner",
    "workPreference": "Remote",
    "preferredOpportunityTypes": ["Internship"],
}
OPPORTUNITY = {
    "id": "test-internship",
    "title": "Python Software Engineering Internship",
    "organization": "Example Org",
    "category": "Internship",
    "description": "Open to undergraduate students with Python skills.",
    "officialUrl": "https://example.org/internship",
}


def _request(q="software", **filters):
    return AgentWorkflowRequest(q=q, **filters)


def test_successful_workflow_uses_real_scoring_and_requires_review():
    calls = []
    analysis_calls = []

    async def search_fn(**kwargs):
        calls.append(kwargs)
        return {
            "source_mode": "live_search",
            "provider": "Tavily Search API",
            "query_used": "software internship",
            "opportunities": [
                OPPORTUNITY,
                {**OPPORTUNITY, "id": "test-internship-2", "title": "Another Python Internship"},
            ],
        }

    async def analyze_fn(opportunity, profile):
        analysis_calls.append(opportunity)
        assert opportunity == OPPORTUNITY
        assert profile == PROFILE
        return {
            "explanation": "Your Python skills match the listing.",
            "concerns": "Verify the current requirements.",
            "recommended_steps": "Review the official listing.",
        }

    result = asyncio.run(
        run_agent_workflow(
            _request(category=["Internship"], location="Remote"),
            PROFILE,
            search_fn,
            main.compute_match_score,
            analyze_fn,
            llm_available=True,
        )
    )

    assert calls == [
        {
            "q": "software",
            "category": ["Internship"],
            "location": "Remote",
            "work_mode": None,
            "education": None,
            "refresh": False,
        }
    ]
    assert result["status"] == "completed"
    assert result["source_mode"] == "live_search"
    assert result["results"][0]["match"] == main.compute_match_score(OPPORTUNITY, PROFILE)
    assert result["results"][0]["analysis"]["source"] == "existing_analyzer"
    assert analysis_calls == [OPPORTUNITY]
    assert result["results"][1]["analysis"]["source"] == "deterministic_fallback"
    assert result["human_review"]["required"] is True
    assert "official" in result["human_review"]["message"].lower()


def test_invalid_query_skips_search():
    calls = []

    async def search_fn(**kwargs):
        calls.append(kwargs)
        return {"opportunities": []}

    result = asyncio.run(
        run_agent_workflow(
            _request("   "),
            PROFILE,
            search_fn,
            main.compute_match_score,
            lambda opportunity, profile: {},
            llm_available=False,
        )
    )

    assert result["status"] == "invalid_input"
    assert result["errors"] == ["A search query is required."]
    assert calls == []
    assert result["human_review"]["required"] is False


def test_empty_search_returns_no_opportunities():
    async def search_fn(**kwargs):
        return {"source_mode": "live_search", "opportunities": []}

    result = asyncio.run(
        run_agent_workflow(
            _request(),
            PROFILE,
            search_fn,
            main.compute_match_score,
            lambda opportunity, profile: {},
            llm_available=False,
        )
    )

    assert result["status"] == "no_opportunities"
    assert result["results"] == []
    assert result["human_review"]["required"] is False


def test_search_failure_is_reported_without_fabricated_results():
    async def search_fn(**kwargs):
        raise RuntimeError("private query must not be logged")

    result = asyncio.run(
        run_agent_workflow(
            _request(),
            PROFILE,
            search_fn,
            main.compute_match_score,
            lambda opportunity, profile: {},
            llm_available=False,
        )
    )

    assert result["status"] == "search_failed"
    assert result["source_mode"] == "unavailable"
    assert result["results"] == []
    assert "unavailable" in result["errors"][0].lower()


def test_scoring_failure_is_reported_and_skips_explanations():
    async def search_fn(**kwargs):
        return {"opportunities": [OPPORTUNITY]}

    def score_fn(opportunity, profile):
        raise RuntimeError("scoring failure")

    result = asyncio.run(
        run_agent_workflow(
            _request(),
            PROFILE,
            search_fn,
            score_fn,
            lambda opportunity, profile: {},
            llm_available=False,
        )
    )

    assert result["status"] == "matching_failed"
    assert result["results"] == []
    assert "could not be completed" in result["errors"][0].lower()


def test_existing_scoring_function_is_used_without_replacement():
    scored = {"score": 81, "classification": "Likely match", "positiveNotes": ["Existing scorer"], "concerns": []}
    calls = []

    async def search_fn(**kwargs):
        return {"opportunities": [OPPORTUNITY]}

    def score_fn(opportunity, profile):
        calls.append((opportunity, profile))
        return scored

    async def analyze_fn(opportunity, profile):
        return {"explanation": "Grounded existing analysis."}

    result = asyncio.run(
        run_agent_workflow(
            _request(),
            PROFILE,
            search_fn,
            score_fn,
            analyze_fn,
            llm_available=True,
        )
    )

    assert calls == [(OPPORTUNITY, PROFILE)]
    assert result["results"][0]["match"] is scored
    assert result["results"][0]["match"]["score"] == 81


def test_analysis_failure_uses_deterministic_fallback():
    async def search_fn(**kwargs):
        return {"opportunities": [OPPORTUNITY]}

    async def analyze_fn(opportunity, profile):
        raise RuntimeError("LLM unavailable")

    result = asyncio.run(
        run_agent_workflow(
            _request(),
            PROFILE,
            search_fn,
            main.compute_match_score,
            analyze_fn,
            llm_available=True,
        )
    )

    analysis = result["results"][0]["analysis"]
    assert analysis["source"] == "deterministic_fallback"
    assert analysis["explanation"]
    assert any("deterministic match notes" in warning for warning in result["warnings"])


def test_missing_profile_fields_are_reported_and_search_continues():
    async def search_fn(**kwargs):
        return {"opportunities": [OPPORTUNITY]}

    result = asyncio.run(
        run_agent_workflow(
            _request(),
            {},
            search_fn,
            main.compute_match_score,
            lambda opportunity, profile: {},
            llm_available=False,
        )
    )

    assert result["status"] == "completed"
    assert "education level" in result["missing_profile_fields"]
    assert result["warnings"]
    assert result["results"][0]["match"]["missingInfo"]


def test_workflow_endpoint_is_authenticated_and_uses_existing_functions(monkeypatch):
    async def fake_profile(user):
        return {"status": "success", "profile": PROFILE}

    async def fake_search(**kwargs):
        return {
            "source_mode": "seed_index",
            "provider": "Curated Index",
            "opportunities": [OPPORTUNITY],
        }

    async def fake_analysis(payload):
        return {
            "explanation": "Example explanation.",
            "concerns": None,
            "recommended_steps": "Check the official portal.",
        }

    monkeypatch.setattr(main, "get_profile", fake_profile)
    monkeypatch.setattr(main, "search_opportunities", fake_search)
    monkeypatch.setattr(main, "analyze_opportunity", fake_analysis)

    unauthorized = client.post("/api/agent/workflow", json={"q": "software"})
    assert unauthorized.status_code == 401

    response = client.post(
        "/api/agent/workflow",
        headers={"Authorization": "Bearer demo_token_guest"},
        json={"q": "software"},
    )
    assert response.status_code == 200
    assert response.json()["source_mode"] == "seed_index"
    assert response.json()["results"][0]["analysis"]["explanation"] == "Example explanation."


def test_existing_search_and_analyze_endpoint_contracts_remain(monkeypatch):
    monkeypatch.setattr(main, "SEARCH_API_KEY", "")
    search_response = client.get("/api/opportunities/search?q=software")
    assert search_response.status_code == 200
    assert {"status", "total", "source_mode", "provider", "opportunities"} <= search_response.json().keys()

    monkeypatch.setattr(main, "GEMINI_API_KEY", "")
    analyze_response = client.post(
        "/api/opportunities/analyze",
        json={
            "opportunity": OPPORTUNITY,
            "profile": PROFILE,
        },
    )
    assert analyze_response.status_code == 200
    assert {
        "match_score",
        "classification",
        "factors",
        "explanation",
        "concerns",
        "recommended_steps",
        "disclaimer",
    } <= analyze_response.json().keys()


def test_existing_analyzer_sends_gemini_key_in_header(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"explanation":"Grounded explanation.",'
                                        '"concerns":"Verify details.",'
                                        '"recommended_steps":"Check the official portal."}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, timeout):
            assert timeout == 10.0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers, json):
            captured.update({"url": url, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(main, "GEMINI_API_KEY", "test-key-never-log")
    monkeypatch.setattr(main.httpx, "AsyncClient", FakeAsyncClient)

    response = client.post(
        "/api/opportunities/analyze",
        json={"opportunity": OPPORTUNITY, "profile": PROFILE},
    )

    assert response.status_code == 200
    assert "test-key-never-log" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "test-key-never-log"
    assert response.json()["explanation"] == "Grounded explanation."