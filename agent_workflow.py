import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

logger = logging.getLogger("pathora_ai.agent_workflow")

_PROFILE_FIELDS = (
    "educationLevel",
    "fieldOfStudy",
    "skills",
    "experienceLevel",
    "workPreference",
    "preferredOpportunityTypes",
)
_EXPLANATION_LIMIT = 1


class AgentWorkflowRequest(BaseModel):
    q: str = Field(max_length=250)
    category: list[str] | None = None
    location: str | None = None
    work_mode: str | None = None
    education: str | None = None
    refresh: bool = False


class AgentState(TypedDict, total=False):
    query: str
    filters: dict[str, Any]
    profile: dict[str, Any]
    missing_profile_fields: list[str]
    opportunities: list[dict[str, Any]]
    matches: list[dict[str, Any]]
    source_mode: str
    provider: str
    query_used: str
    status: str
    errors: list[str]
    warnings: list[str]
    requires_human_review: bool
    review_message: str
    result: dict[str, Any]


SearchFunction = Callable[..., Awaitable[dict[str, Any]]]
ScoreFunction = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
AnalysisFunction = Callable[
    [dict[str, Any], dict[str, Any]],
    Awaitable[dict[str, Any]] | dict[str, Any],
]


def _safe_profile(profile: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for field in _PROFILE_FIELDS:
        value = profile.get(field)
        if field in ("skills", "preferredOpportunityTypes"):
            safe[field] = (
                [item.strip() for item in value if isinstance(item, str) and item.strip()]
                if isinstance(value, list)
                else []
            )
        else:
            safe[field] = value.strip() if isinstance(value, str) else ""
    return safe


def build_agent_graph(
    search_fn: SearchFunction,
    score_fn: ScoreFunction,
    analyze_fn: AnalysisFunction,
    llm_available: bool,
):
    async def validate_input(state: AgentState) -> dict[str, Any]:
        query = state.get("query", "").strip()
        if not query:
            return {
                "status": "invalid_input",
                "errors": ["A search query is required."],
                "missing_profile_fields": [],
            }

        profile = _safe_profile(state.get("profile", {}))
        missing_fields = [
            label
            for field, label in (
                ("educationLevel", "education level"),
                ("fieldOfStudy", "field of study"),
                ("skills", "skills"),
                ("experienceLevel", "experience level"),
            )
            if not profile[field]
        ]
        return {
            "query": query,
            "profile": profile,
            "missing_profile_fields": missing_fields,
            "status": "ready",
        }

    def route_after_validation(state: AgentState) -> str:
        if state.get("status") == "invalid_input":
            return "complete"
        return "profile_notice" if state.get("missing_profile_fields") else "search"

    def note_incomplete_profile(state: AgentState) -> dict[str, Any]:
        warnings = list(state.get("warnings", []))
        missing = ", ".join(state.get("missing_profile_fields", []))
        warnings.append(f"Profile information is incomplete ({missing}); match estimates may be less informative.")
        return {"warnings": warnings}

    async def search_opportunities(state: AgentState) -> dict[str, Any]:
        filters = state.get("filters", {})
        try:
            search_result = await search_fn(
                q=state["query"],
                category=filters.get("category"),
                location=filters.get("location"),
                work_mode=filters.get("work_mode"),
                education=filters.get("education"),
                refresh=filters.get("refresh", False),
            )
            if not isinstance(search_result, dict) or not isinstance(search_result.get("opportunities"), list):
                raise ValueError("Invalid search response")
            opportunities = [
                opportunity
                for opportunity in search_result["opportunities"]
                if isinstance(opportunity, dict)
            ]
            warnings = list(state.get("warnings", []))
            source_mode = str(search_result.get("source_mode", "unknown"))
            if source_mode == "seed_index":
                warnings.append("Showing curated demo opportunities because live search did not return usable listings.")
            return {
                "opportunities": opportunities,
                "source_mode": source_mode,
                "provider": str(search_result.get("provider", "")),
                "query_used": str(search_result.get("query_used", state["query"])),
                "status": "searched" if opportunities else "no_opportunities",
                "warnings": warnings,
            }
        except Exception as error:
            logger.warning("Agent search failed (%s)", type(error).__name__)
            return {
                "opportunities": [],
                "source_mode": "unavailable",
                "status": "search_failed",
                "errors": ["Opportunity search is unavailable. Please try again later."],
            }

    def route_after_search(state: AgentState) -> str:
        if state.get("status") == "search_failed" or not state.get("opportunities"):
            return "review"
        return "match"

    def evaluate_matches(state: AgentState) -> dict[str, Any]:
        try:
            matches = [
                {
                    "opportunity": opportunity,
                    "match": score_fn(opportunity, state["profile"]),
                }
                for opportunity in state["opportunities"]
            ]
            matches.sort(key=lambda result: result["match"]["score"], reverse=True)
            return {"matches": matches, "status": "matched"}
        except Exception as error:
            logger.warning("Agent matching failed (%s)", type(error).__name__)
            return {
                "matches": [],
                "status": "matching_failed",
                "errors": ["Match evaluation could not be completed."],
            }

    def route_after_matching(state: AgentState) -> str:
        return "explain" if state.get("matches") else "review"

    async def generate_explanations(state: AgentState) -> dict[str, Any]:
        matches = [dict(result) for result in state.get("matches", [])]
        warnings = list(state.get("warnings", []))
        for result in matches[:_EXPLANATION_LIMIT]:
            opportunity = result["opportunity"]
            score = result["match"]
            fallback_explanation = (
                " ".join(score.get("positiveNotes", []))
                or "Opportunity alignment is estimated from the available profile and listing information."
            )
            fallback_concerns = " ".join(score.get("concerns", [])) or None
            result["analysis"] = {
                "explanation": fallback_explanation,
                "concerns": fallback_concerns,
                "recommended_steps": "Review the official listing and verify eligibility requirements and deadlines.",
                "source": "deterministic_fallback",
            }
            try:
                analysis = analyze_fn(opportunity, state["profile"])
                if inspect.isawaitable(analysis):
                    analysis = await analysis
                if not isinstance(analysis, dict):
                    raise ValueError("Invalid analysis response")
                explanation = analysis.get("explanation")
                if isinstance(explanation, str) and explanation.strip():
                    result["analysis"]["explanation"] = explanation
                    if llm_available and explanation != fallback_explanation:
                        result["analysis"]["source"] = "existing_analyzer"
                concerns = analysis.get("concerns")
                if isinstance(concerns, str) or concerns is None:
                    result["analysis"]["concerns"] = concerns
                steps = analysis.get("recommended_steps")
                if isinstance(steps, str) and steps.strip():
                    result["analysis"]["recommended_steps"] = steps
            except Exception as error:
                logger.warning("Agent explanation fallback used (%s)", type(error).__name__)
                warning = "AI explanation was unavailable for one or more results; deterministic match notes are shown."
                if warning not in warnings:
                    warnings.append(warning)

        for result in matches[_EXPLANATION_LIMIT:]:
            score = result["match"]
            result["analysis"] = {
                "explanation": " ".join(score.get("positiveNotes", []))
                or "Opportunity alignment is estimated from the available profile and listing information.",
                "concerns": " ".join(score.get("concerns", [])) or None,
                "recommended_steps": "Review the official listing and verify eligibility requirements and deadlines.",
                "source": "deterministic_fallback",
            }
        return {"matches": matches, "warnings": warnings}

    def mark_human_review(state: AgentState) -> dict[str, Any]:
        has_results = bool(state.get("matches"))
        status = "completed" if state.get("status") == "matched" else state.get("status", "completed")
        return {
            "requires_human_review": has_results,
            "review_message": (
                "Verify official eligibility requirements and deadlines on each opportunity portal before relying on these match estimates."
                if has_results
                else "No matched opportunities are available to review. Try another search or check back later."
            ),
            "status": status,
        }

    def complete(state: AgentState) -> dict[str, Any]:
        return {
            "result": {
                "status": state.get("status", "completed"),
                "query": state.get("query", ""),
                "query_used": state.get("query_used", ""),
                "source_mode": state.get("source_mode", "not_searched"),
                "provider": state.get("provider", ""),
                "results": state.get("matches", []),
                "missing_profile_fields": state.get("missing_profile_fields", []),
                "warnings": state.get("warnings", []),
                "errors": state.get("errors", []),
                "human_review": {
                    "required": state.get("requires_human_review", False),
                    "message": state.get("review_message", "Review the official opportunity portal before relying on listing details."),
                },
            }
        }

    graph = StateGraph(AgentState)
    graph.add_node("validate_input", validate_input)
    graph.add_node("note_incomplete_profile", note_incomplete_profile)
    graph.add_node("search_opportunities", search_opportunities)
    graph.add_node("evaluate_matches", evaluate_matches)
    graph.add_node("generate_explanations", generate_explanations)
    graph.add_node("human_review_checkpoint", mark_human_review)
    graph.add_node("complete", complete)

    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges(
        "validate_input",
        route_after_validation,
        {
            "complete": "complete",
            "profile_notice": "note_incomplete_profile",
            "search": "search_opportunities",
        },
    )
    graph.add_edge("note_incomplete_profile", "search_opportunities")
    graph.add_conditional_edges(
        "search_opportunities",
        route_after_search,
        {"review": "human_review_checkpoint", "match": "evaluate_matches"},
    )
    graph.add_conditional_edges(
        "evaluate_matches",
        route_after_matching,
        {"review": "human_review_checkpoint", "explain": "generate_explanations"},
    )
    graph.add_edge("generate_explanations", "human_review_checkpoint")
    graph.add_edge("human_review_checkpoint", "complete")
    graph.add_edge("complete", END)
    return graph.compile()


async def run_agent_workflow(
    request: AgentWorkflowRequest,
    profile: dict[str, Any],
    search_fn: SearchFunction,
    score_fn: ScoreFunction,
    analyze_fn: AnalysisFunction,
    llm_available: bool,
) -> dict[str, Any]:
    graph = build_agent_graph(search_fn, score_fn, analyze_fn, llm_available)
    initial_state: AgentState = {
        "query": request.q,
        "filters": request.model_dump(exclude={"q"}),
        "profile": _safe_profile(profile),
        "opportunities": [],
        "matches": [],
        "errors": [],
        "warnings": [],
        "source_mode": "not_searched",
        "requires_human_review": False,
    }
    final_state = await graph.ainvoke(initial_state)
    return final_state["result"]