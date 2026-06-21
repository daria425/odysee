from langchain_core.tools import tool, StructuredTool
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from app.lib.models import TravelResponse
from app.lib.tavily_search import tavily_client


@tool
def search_nightlife(nightlife_query: str) -> list[dict]:
    """
    Search for nightlife activities in a city.
    The query should include the city name and the type of nightlife activities (e.g., bars, clubs, live music).
    Returns a list of recommended nightlife spots based on the query.
    Args:
        nightlife_query (str): A string containing a nightlife-related search (e.g city name + 'live music').
    """
    results = tavily_client.search(nightlife_query, max_results=6)
    return [
        {"title": r["title"], "content": r["content"], "url": r["url"]}
        for r in results["results"]
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
    results = tavily_client.search(budget_query, max_results=6)
    return [
        {"title": r["title"], "content": r["content"], "url": r["url"]}
        for r in results["results"]
    ]


def make_budget_agent_tool(llm, prompt):
    agent = create_agent(llm, tools=[search_budget], system_prompt=prompt)

    @tool
    def call_budget_agent(query: str) -> str:
        """Call the budget specialist agent for cost estimates, daily spend, and money-saving tips."""
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
        return result["messages"][-1].content

    return call_budget_agent


@tool
def search_side_quests(query: str) -> list[dict]:
    """
    Search the web for local, off-beat activities and experiences at a destination.
    The query should include the destination, time context, and any relevant constraints from the conversation.
    Returns a list of activity results with titles, content, and URLs.
    Args:
        query (str): A search query including destination and context (e.g. 'unusual local activities Tbilisi afternoon solo').
    """
    results = tavily_client.search(query, max_results=6)
    return [
        {"title": r["title"], "content": r["content"], "url": r["url"]}
        for r in results["results"]
    ]


def make_side_quest_agent_tool(llm, prompt):
    agent = create_agent(llm, tools=[search_side_quests], system_prompt=prompt)

    @tool
    def call_side_quest_agent(query: str) -> str:
        """Call the side quest agent to find unusual, local, off-beat activities at a destination. Include destination, time of day, energy level, and any activities already done in the query."""
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
        return result["messages"][-1].content

    return call_side_quest_agent


def make_nightlife_agent_tool(llm, prompt):
    agent = create_agent(llm, tools=[search_nightlife], system_prompt=prompt)

    @tool
    def call_nightlife_agent(query: str) -> str:
        """Call the nightlife specialist agent for clubs, bars, and music scene research."""
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
        return result["messages"][-1].content

    return call_nightlife_agent
