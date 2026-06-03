from pydantic import BaseModel, Field
from typing import Optional

class TravelResponse(BaseModel):
    chat_response:str
    recommendations: list[str] = Field(default_factory=list, description="list of recommendations if relevant to the users query, otherwise empty list")
    warnings: Optional[str] = Field(default=None, description="any warnings or disclaimers relevant to the users query, otherwise None")
    follow_up: Optional[str] = Field(default=None, description="any follow up questions or suggestions relevant to the users query, otherwise None. Place any subsequent questions hereinstead of in chat_response")

