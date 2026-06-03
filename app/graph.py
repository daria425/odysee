from typing import Annotated
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

load_dotenv()  # Load environment variables from .env file

class State(TypedDict):
    messages: Annotated[list, add_messages]


llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.2)


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

workflow = graph_builder.compile()
