from __future__ import annotations

from typing import TypedDict

from typing_extensions import Annotated

from pydantic import BaseModel, Field
import operator


class OverallState(TypedDict):
    search_query: Annotated[list, operator.add]
    web_research_result: Annotated[list, operator.add]
    sources_gathered: Annotated[list, operator.add]
    destination: str
    travel_date: str


class Query(TypedDict):
    query: str
    rationale: str


class QueryGenerationState(TypedDict):
    search_query: Annotated[list[Query], operator.add]


class WebSearchState(TypedDict):
    search_query: str
    id: str


class SearchStateOutput(BaseModel):
    running_summary: str = Field(default=None)  # Final report
