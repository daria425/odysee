from app.agent.research.state import OverallState, QueryGenerationState
from app.agent.research.configuration import Configuration
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
    llm = ChatAnthropic(model_name=configuration.model,
                        temperature=0.2, api_key=os.getenv("ANTHROPIC_API_KEY"))
    question_list = load_questions()
    year = date.today().year
    system_prompt = load_prompt("app/lib/prompts/generate_queries_prompt.txt",
                                year=year, destination=state["destination"], key_questions=question_list)
