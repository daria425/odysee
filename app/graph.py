from typing import Annotated
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, AIMessage
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from app.lib.utils import load_prompt, load_profile
from app.lib.models import TravelResponse


def build_workflow(chat_llm: BaseChatModel = None):
    profile = load_profile()

    class State(TypedDict):
        messages: Annotated[list, add_messages]
        responses: list[TravelResponse]

    MESSAGE_WINDOW = 10

    def trim_messages(state: State):
        # Trim the message history to the last MESSAGE_WINDOW messages to prevent context overflow, naive for now
        return {"messages": state["messages"][-MESSAGE_WINDOW:]}

    def chatbot(state: State):
        system_prompt = load_prompt(
            "app/lib/prompts/chat_prompt.txt", user_profile=profile)
        response: TravelResponse = chat_llm.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"])
        return {
            "messages": [AIMessage(content=response.chat_response)],
            "responses": state.get("responses", []) + [response],
        }

    graph_builder = StateGraph(State)
    graph_builder.add_node("trim_messages", trim_messages)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_edge(START, "trim_messages")
    graph_builder.add_edge("trim_messages", "chatbot")
    graph_builder.add_edge("chatbot", END)

    checkpointer = InMemorySaver()
    workflow = graph_builder.compile(checkpointer=checkpointer)
    return workflow
