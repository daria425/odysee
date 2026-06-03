from typing import Annotated
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, AIMessage
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from app.lib.utils import load_prompt, load_profile
from app.lib.models import TravelResponse


load_dotenv()

profile = load_profile()

class State(TypedDict):
    messages: Annotated[list, add_messages]
    responses: list[TravelResponse]


llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.2)
structured_llm = llm.with_structured_output(TravelResponse)


def chatbot(state: State):
    system_prompt = load_prompt("app/lib/prompts/chat_prompt.txt", user_profile=profile)
    response: TravelResponse = structured_llm.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    return {
        "messages": [AIMessage(content=response.chat_response)],
        "responses": state.get("responses", []) + [response],
    }


graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

workflow = graph_builder.compile()
