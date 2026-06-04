from pydantic import BaseModel, Field
from typing import Optional


class TravelResponse(BaseModel):
    chat_response: str
    recommendations: Optional[list[str]] = Field(
        default_factory=list, description="list of recommendations if relevant to the users query, otherwise empty list")
    warnings: Optional[list[str]] = Field(
        default_factory=list, description="any warnings or disclaimers relevant to the users query, otherwise empty list")
    follow_up: Optional[list[str]] = Field(
        default_factory=list, description="any follow up questions or suggestions relevant to the users query, otherwise empty list. Place any subsequent questions here instead of in chat_response")
