from __future__ import annotations

from typing import TypedDict

from typing_extensions import Annotated

from pydantic import BaseModel, Field
import operator


class OverallState(TypedDict):
    search_queries: Annotated[list[dict], operator.add]
    web_research_result: Annotated[list[dict], operator.add]
    sources_gathered: Annotated[list, operator.add]
    destination: str
    travel_date: str
    report: str


class QueryGenerationState(TypedDict):
    search_queries: Annotated[list[dict], operator.add]


class WebSearchState(TypedDict):
    search_query: str
    question: str
    id: int


class SearchStateOutput(BaseModel):
    report: str = Field(default=None)
