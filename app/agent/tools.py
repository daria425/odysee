import json
from pathlib import Path
from langchain_core.tools import tool, StructuredTool
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from app.lib.models import TravelResponse

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "search"


@tool
def search_nightlife(nightlife_query: str) -> list[dict]:
    """
    Search for nightlife activities in a city.
    The query should include the city name and the type of nightlife activities (e.g., bars, clubs, live music).
    Returns a list of recommended nightlife spots based on the query.
    Args:
        nightlife_query (str): A string containing a nightlife-related search (e.g city name + 'live music').
    """
    with open(DATA_DIR / "nightlife.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        {"title": r["title"], "content": r["content"], "url": r["url"]}
        for r in data["results"]
    ]


def make_respond_tool():
    return StructuredTool.from_function(
        func=lambda **kwargs: TravelResponse(**kwargs),
        name="respond",
        description="Use this to give your final answer to the user.",
        args_schema=TravelResponse,
    )


@tool
def search_budget(budget_query: str) -> list[dict]:
    """
    Search for budget and cost information for a destination.
    The query should include the city name and cost category (e.g., accommodation, food, transport).
    Returns a list of budget-related results based on the query.
    Args:
        budget_query (str): A string containing a budget-related search (e.g city name + 'daily costs').
    """
    with open(DATA_DIR / "budget.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        {"title": r["title"], "content": r["content"], "url": r["url"]}
        for r in data["results"]
    ]


def make_budget_agent_tool(llm, prompt):
    agent = create_agent(llm, tools=[search_budget], system_prompt=prompt)

    @tool
    def call_budget_agent(query: str) -> str:
        """Call the budget specialist agent for cost estimates, daily spend, and money-saving tips."""
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
        return result["messages"][-1].content

    return call_budget_agent


def make_nightlife_agent_tool(llm, prompt):
    agent = create_agent(llm, tools=[search_nightlife], system_prompt=prompt)

    @tool
    def call_nightlife_agent(query: str) -> str:
        """Call the nightlife specialist agent for clubs, bars, and music scene research."""
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
        return result["messages"][-1].content

    return call_nightlife_agent
