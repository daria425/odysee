import logging
from app.agent.research.state import OverallState, WebSearchState
from app.agent.research.configuration import Configuration
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic
from app.lib.models import SearchQueryList, RegenerateResponse, RegeneratedQueryList
from langgraph.types import Send
from app.lib.utils import load_prompt, load_questions
from app.lib.tavily_search import tavily_client
from dotenv import load_dotenv
from datetime import date
import os
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

load_dotenv()


def generate_queries(state: OverallState, config: RunnableConfig):

    configuration = Configuration.from_runnable_config(config)
    llm = ChatAnthropic(model_name=configuration.question_generator_model,
                        temperature=0.2, api_key=os.getenv("ANTHROPIC_API_KEY")).with_structured_output(SearchQueryList)
    question_list = load_questions()
    year = date.today().year
    system_prompt = load_prompt("app/lib/prompts/generate_queries_prompt.txt",
                                year=year, destination=state["destination"], travel_date=state["travel_date"])
    user_msg = f"""
    Here are some questions I have about {state['destination']}:\n\n
    {question_list['key_questions']}
    """
    messages = [SystemMessage(content=system_prompt),
                HumanMessage(content=user_msg)]
    response: SearchQueryList = llm.invoke(messages)
    formatted_queries = [
        {"question": q, "search_query": s, "id": i} for i, (q, s) in enumerate(response.queries.items())
    ]
    return {
        "pending_queries": formatted_queries,
        "search_queries": formatted_queries
    }


def create_web_research_nodes(state: OverallState):
    return [
        Send("web_research", {
            "search_query": item["search_query"],
            "question": item["question"],
            "id": item["id"],
        })
        for item in state["pending_queries"]
    ]


def web_research(state: WebSearchState, config: RunnableConfig):
    configuration = Configuration.from_runnable_config(config)
    results = tavily_client.search(
        state["search_query"], max_results=configuration.max_search_results)["results"]
    context = "\n\n".join(
        f"Source: {r['title']}\nURL: {r['url']}\n{r['content']}" for r in results)
    sources = [{"url": r["url"], "title": r["title"]} for r in results]

    llm = ChatAnthropic(model_name=configuration.research_model,
                        temperature=0, api_key=os.getenv("ANTHROPIC_API_KEY"))
    system_prompt = load_prompt("app/lib/prompts/web_researcher_prompt.txt")
    user_msg = f"Question: {state['question']}\n\nSearch results:\n{context}"
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)])

    return {
        "sources_gathered": sources,
        "web_research_result": [{"question": state["question"], "answer": response.content, "search_query": state["search_query"]}],
    }


def should_regenerate(state: OverallState, config: RunnableConfig):
    configuration = Configuration.from_runnable_config(config)
    if state.get("reflection_count", 0) >= configuration.max_reflections:
        return {"queries_to_regenerate": [], "reflection_count": state.get("reflection_count", 0) + 1}
    llm = ChatAnthropic(model_name=configuration.judge_model,
                        temperature=0, api_key=os.getenv("ANTHROPIC_API_KEY")).with_structured_output(RegenerateResponse)
    system_prompt = load_prompt("app/lib/prompts/should_regenerate_prompt.txt")
    user_msg = f"""
    Here is the list of web search queries and their results:
    {state['web_research_result']}
    """
    response: RegenerateResponse = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)])
    results = state["web_research_result"]
    queries_to_regenerate = [
        {
            "initial_user_question": results[item.item_index]["question"],
            "prev_generated_query": results[item.item_index]["search_query"],
            "output_feedback": item.feedback,
        }
        for item in (response.queries_to_regenerate or [])
    ]
    return {
        "queries_to_regenerate": queries_to_regenerate,
        "reflection_count": state.get("reflection_count", 0) + 1,
    }


def route_after_reflection(state: OverallState):
    if state.get("queries_to_regenerate"):
        return "regenerate_queries"
    return "finalize_answer"


def finalize_answer(state: OverallState, config: RunnableConfig):
    configuration = Configuration.from_runnable_config(config)
    llm = ChatAnthropic(model_name=configuration.synthesis_model,
                        temperature=0.3, api_key=os.getenv("ANTHROPIC_API_KEY"))
    system_prompt = load_prompt("app/lib/prompts/finalize_answer_prompt.txt",
                                destination=state["destination"], travel_date=state["travel_date"])
    research = "\n\n".join(
        f"Q: {item['question']}\nA: {item['answer']}" for item in state["web_research_result"]
    )
    user_msg = f"Here are the research findings:\n\n{research}"
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)])
    return {"report": response.content}


def regenerate_queries(state: OverallState, config: RunnableConfig):
    configuration = Configuration.from_runnable_config(config)
    llm = ChatAnthropic(model_name=configuration.question_generator_model,
                        temperature=0.2, api_key=os.getenv("ANTHROPIC_API_KEY")).with_structured_output(RegeneratedQueryList)
    system_prompt = load_prompt(
        "app/lib/prompts/regenerate_queries_prompt.txt")
    user_msg = f"""
    Here are the queries that need to be regenerated (prev_generated_query), feedback (output_feedback), and the initial user question (initial_user_question):
    {state['queries_to_regenerate']}
    """
    response: RegeneratedQueryList = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)])
    pending_queries = [
        {"question": item["initial_user_question"],
            "search_query": new_query, "id": i}
        for i, (item, new_query) in enumerate(zip(state["queries_to_regenerate"], response.queries))
    ]
    return {
        "pending_queries": pending_queries,
        "search_queries": pending_queries,
    }


if __name__ == "__main__":
    import json

    state = {
        "destination": "Tbilisi",
        "travel_date": "July 2026",
        "search_queries": [],
        "web_research_result": [],
        "sources_gathered": [],
        "report": "",
    }
    result = generate_queries(state, {"configurable": {}})
    print(json.dumps(result, indent=2))
