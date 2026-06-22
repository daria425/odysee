from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from app.lib.models import TravelResponse


class State(TypedDict):
    messages: Annotated[list, add_messages]
    responses: list[TravelResponse]
    trip_context: str
