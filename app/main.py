import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from app.agent.chat.graph import build_workflow
from app.lib.models import TravelResponse, APIChatResponse, APIChatRequest
from app.lib.db.store import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.2)
    with SqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
        app.state.workflow = build_workflow(llm=llm, checkpointer=checkpointer)
        app.state.langfuse_handler = CallbackHandler()
        yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=APIChatResponse)
def chat(request: APIChatRequest, fastapi_request: Request):
    workflow = fastapi_request.app.state.workflow
    config = {
        "configurable": {"thread_id": request.thread_id},
        "callbacks": [app.state.langfuse_handler],
        "metadata": {"langfuse_session_id": request.langfuse_session_id}
    }
    logger.info("chat request thread=%s", request.thread_id)
    state = workflow.invoke(
        {"messages": [HumanMessage(content=request.user_message)]},
        config=config,
    )

    if state.get("responses"):
        travel: TravelResponse = state["responses"][-1]
    else:
        travel = TravelResponse(chat_response=state["messages"][-1].content)

    return APIChatResponse(thread_id=request.thread_id, langfuse_session_id=request.langfuse_session_id, **travel.model_dump())
