from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from app.agent.chat.state import State
from app.agent.chat.nodes import trim_messages, make_call_model, format_response, make_log_memory, make_inject_context
from app.lib.db.store import MemoryStore
from app.agent.chat.tools import make_nightlife_agent_tool, make_budget_agent_tool, make_side_quest_agent_tool, make_respond_tool
from app.lib.utils import load_profile, load_prompt


def should_continue(state):
    last = state["messages"][-1]
    if not last.tool_calls:
        return "format_response"
    if last.tool_calls[0]["name"] == "respond":
        return "format_response"
    return "tool_node"


def build_workflow(llm: BaseChatModel, checkpointer: BaseCheckpointSaver):
    profile = load_profile()

    nightlife_prompt = load_prompt("app/lib/prompts/nightlife_research_prompt.txt", user_profile=profile)
    nightlife_tool = make_nightlife_agent_tool(llm, nightlife_prompt)
    budget_prompt = load_prompt("app/lib/prompts/budget_research_prompt.txt", user_profile=profile)
    budget_tool = make_budget_agent_tool(llm, budget_prompt)
    side_quest_prompt = load_prompt("app/lib/prompts/side_quest_research_prompt.txt", user_profile=profile)
    side_quest_tool = make_side_quest_agent_tool(llm, side_quest_prompt)
    respond_tool = make_respond_tool()
    chatbot_tools = [nightlife_tool, budget_tool, side_quest_tool, respond_tool]

    store = MemoryStore()

    builder = StateGraph(State)
    builder.add_node("trim_messages", trim_messages)
    builder.add_node("inject_context", make_inject_context(store))
    builder.add_node("call_model", make_call_model(llm, profile, chatbot_tools))
    builder.add_node("tool_node", ToolNode(chatbot_tools))
    builder.add_node("format_response", format_response)
    builder.add_node("log_memory", make_log_memory(store))
    builder.add_edge(START, "trim_messages")
    builder.add_edge("trim_messages", "inject_context")
    builder.add_edge("inject_context", "call_model")
    builder.add_conditional_edges("call_model", should_continue)
    builder.add_edge("tool_node", "call_model")
    builder.add_edge("format_response", "log_memory")
    builder.add_edge("log_memory", END)

    return builder.compile(checkpointer=checkpointer)
