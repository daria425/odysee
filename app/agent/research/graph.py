from app.agent.research.nodes import generate_queries, create_web_research_nodes, web_research, finalize_answer
from app.agent.research.state import OverallState as State
from app.agent.research.configuration import Configuration
from langgraph.graph import StateGraph, START, END

builder = StateGraph(State, config_schema=Configuration)

builder.add_node("generate_queries", generate_queries)
builder.add_node("web_research", web_research)
builder.add_node("finalize_answer", finalize_answer)

builder.add_edge(START, "generate_queries")
# Add conditional edge to continue with search queries in a parallel branch
builder.add_conditional_edges(
    "generate_queries", create_web_research_nodes, ["web_research"]
)
builder.add_edge("web_research", "finalize_answer")
builder.add_edge("finalize_answer", END)
workflow = builder.compile()
