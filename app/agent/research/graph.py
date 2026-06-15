from app.agent.research.nodes import generate_queries, create_web_research_nodes, web_research, finalize_answer, should_regenerate, route_after_reflection
from app.agent.research.state import OverallState as State
from app.agent.research.configuration import Configuration
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

builder = StateGraph(State, config_schema=Configuration)

builder.add_node("generate_queries", generate_queries)
builder.add_node("web_research", web_research)
builder.add_node("finalize_answer", finalize_answer)

builder.add_edge(START, "generate_queries")
# Add conditional edge to continue with search queries in a parallel branch
builder.add_conditional_edges(
    "generate_queries", create_web_research_nodes, ["web_research"]
)
builder.add_edge("web_research", "should_regenerate")
# builder.add_edge("web_research", "finalize_answer")
builder.add_conditional_edges("should_regenerate", route_after_reflection, [
                              "regenerate_queries", "finalize_answer"])
builder.add_conditional_edges(
    "regenerate_queries", create_web_research_nodes, ["web_research"])
builder.add_edge("finalize_answer", END)
workflow = builder.compile(checkpointer=InMemorySaver())

if __name__ == "__main__":
    from dotenv import load_dotenv
    from langfuse.langchain import CallbackHandler
    from uuid import uuid4
    import json

    load_dotenv()
    langfuse_handler = CallbackHandler()

    session_id = f"test-chat-session-{str(uuid4())}"
    thread_id = f"test-chat-thread-{str(uuid4())}"
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [langfuse_handler],
        "metadata": {"langfuse_session_id": session_id}
    }
    state = {
        "destination": "Tbilisi",
        "travel_date": "July 2026",
        "search_queries": [],
        "web_research_result": [],
        "sources_gathered": [],
        "report": "",
    }
    result = workflow.invoke(state, config)
    print(json.dumps(result, indent=2))
