from app.agent.research.state import OverallState, QueryGenerationState
from app.agent.research.configuration import Configuration
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic
from app.lib.models import SearchQueryList
from app.lib.utils import load_prompt, load_questions
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
