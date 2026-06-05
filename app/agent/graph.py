from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from app.agent.state import State
from app.agent.nodes import trim_messages, make_chatbot
from app.lib.utils import load_profile


def build_workflow(llm: BaseChatModel):
    profile = load_profile()

    builder = StateGraph(State)
    builder.add_node("trim_messages", trim_messages)
    builder.add_node("chatbot", make_chatbot(llm, profile))
    builder.add_edge(START, "trim_messages")
    builder.add_edge("trim_messages", "chatbot")
    builder.add_edge("chatbot", END)

    return builder.compile(checkpointer=InMemorySaver())
