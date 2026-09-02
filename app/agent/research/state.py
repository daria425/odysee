from __future__ import annotations

from typing import TypedDict

from typing_extensions import Annotated

from pydantic import BaseModel, Field
import operator


class WebSearchState(TypedDict):
    search_query: str
    question: str
    id: int


class QueryToRegenerate(TypedDict):
    id: int
    initial_user_question: str
    prev_generated_query: str
    output_feedback: str


def merge_by_id(existing: list[dict], new: list[dict]) -> list[dict]:
    """Upserts web_research results by id — a regenerated answer replaces the stale one
    for that id instead of accumulating alongside it (plain operator.add would keep both)."""
    merged = {item["id"]: item for item in existing}
    for item in new:
        merged[item["id"]] = item
    return list(merged.values())


class OverallState(TypedDict):
    search_queries: Annotated[list[WebSearchState], operator.add]
    pending_queries: list[WebSearchState]
    queries_to_regenerate: list[QueryToRegenerate]
    web_research_result: Annotated[list[dict], merge_by_id]
    sources_gathered: Annotated[list, operator.add]
    confirmed_ids: Annotated[list[int], operator.add]
    destination: str
    travel_date: str
    report: str
    reflection_count: int


class QueryGenerationState(TypedDict):
    search_queries: Annotated[list[WebSearchState], operator.add]


class SearchStateOutput(BaseModel):
    report: str = Field(default=None)
