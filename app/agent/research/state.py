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
    initial_user_question: str
    prev_generated_query: str
    output_feedback: str


class OverallState(TypedDict):
    search_queries: Annotated[list[WebSearchState], operator.add]
    pending_queries: list[WebSearchState]
    queries_to_regenerate: list[QueryToRegenerate]
    web_research_result: Annotated[list[dict], operator.add]
    sources_gathered: Annotated[list, operator.add]
    destination: str
    travel_date: str
    report: str
    reflection_count: int


class QueryGenerationState(TypedDict):
    search_queries: Annotated[list[WebSearchState], operator.add]


class SearchStateOutput(BaseModel):
    report: str = Field(default=None)
