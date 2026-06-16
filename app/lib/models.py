from pydantic import BaseModel, Field
from typing import Optional, Dict


class TravelResponse(BaseModel):
    chat_response: str
    recommendations: Optional[list[str]] = Field(
        default_factory=list, description="list of recommendations if relevant to the users query, otherwise empty list")
    warnings: Optional[list[str]] = Field(
        default_factory=list, description="any warnings or disclaimers relevant to the users query, otherwise empty list")
    follow_up: Optional[list[str]] = Field(
        default_factory=list, description="any follow up questions or suggestions relevant to the users query, otherwise empty list. Place any subsequent questions here instead of in chat_response")


class APIChatResponse(TravelResponse):
    thread_id: str
    langfuse_session_id: str


class APIChatRequest(BaseModel):
    user_message: str
    thread_id: str
    langfuse_session_id: str


class SearchQueryList(BaseModel):
    queries: Dict[str, str] = Field(
        description="mapping of each key question (exact text) to one focused search query string"
    )


class RegeneratedQueryList(BaseModel):
    queries: list[str] = Field(
        description="list of search queries that need to be regenerated based on feedback"
    )


class QueryToRegenerate(BaseModel):
    item_index: int = Field(
        description="index of the item in the web search results that needs to be regenerated")
    feedback: str = Field(
        description="feedback on why the current search query result is insufficient, to guide regeneration")


class RegenerateResponse(BaseModel):
    queries_to_regenerate: Optional[list[QueryToRegenerate]] = Field(
        default_factory=list, description="list of search queries that need to be regenerated based on feedback, if any")
