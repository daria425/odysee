from typing import Annotated
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, AIMessage
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from app.lib.utils import load_prompt, load_profile



load_dotenv()  # Load environment variables from .env file

profile = load_profile()
class State(TypedDict):
    messages: Annotated[list, add_messages]


llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.2)


def chatbot(state: State):
    system_prompt = load_prompt("app/lib/prompts/chat_prompt.txt", user_profile = profile)
    ai_reply: AIMessage = llm.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    return {
        "messages": [ai_reply]
    }


graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

workflow = graph_builder.compile()
