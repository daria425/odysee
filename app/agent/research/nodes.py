from app.agent.research.state import OverallState, WebSearchState
from app.agent.research.configuration import Configuration
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic
from app.lib.models import SearchQueryList
from langgraph.types import Send
from app.lib.utils import load_prompt, load_questions
from app.lib.tavily_search import tavily_client
from dotenv import load_dotenv
from datetime import date
import os
from langchain_core.runnables import RunnableConfig

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
        "search_queries": formatted_queries
    }


def create_web_research_nodes(state: OverallState):
    return [
        Send("web_research", {
            "search_query": item["search_query"],
            "question": item["question"],
            "id": item["id"],
        })
        for item in state["search_queries"]
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
        "web_research_result": [{"question": state["question"], "answer": response.content}],
    }


def finalize_answer(state: OverallState, config: RunnableConfig):
    configuration = Configuration.from_runnable_config(config)
    llm = ChatAnthropic(model_name=configuration.synthesis_model,
                        temperature=0.3, api_key=os.getenv("ANTHROPIC_API_KEY"))
    system_prompt = load_prompt("app/lib/prompts/finalize_answer.txt",
                                destination=state["destination"], travel_date=state["travel_date"])
    research = "\n\n".join(
        f"Q: {item['question']}\nA: {item['answer']}" for item in state["web_research_result"]
    )
    user_msg = f"Here are the research findings:\n\n{research}"
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)])
    return {"report": response.content}


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
