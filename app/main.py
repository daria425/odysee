import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from app.agent.chat.graph import build_workflow
from app.agent.research.graph import workflow as research_workflow
from app.lib.models import TravelResponse, APIChatResponse, APIChatRequest
from app.lib.db.models import Trip
from app.lib.db.store import DB_PATH, MemoryStore
from app.lib.utils import parse_start_command

logging.basicConfig(level=logging.INFO,
                    format="%(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, trip_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(trip_id, []).append(ws)

    def disconnect(self, trip_id: str, ws: WebSocket):
        conns = self.active.get(trip_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.active.pop(trip_id, None)

    async def broadcast(self, trip_id: str, message: dict):
        for ws in list(self.active.get(trip_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(trip_id, ws)


manager = ConnectionManager()


def _research_status_message(trip: Trip) -> dict:
    return {
        "trip_id": trip.trip_id,
        "status": trip.research_status,
        "report": trip.research_report,
        "error": trip.research_error,
        "research_started_at": trip.research_started_at,
        "research_updated_at": trip.research_updated_at,
    }


async def run_research(store: MemoryStore, trip: Trip, langfuse_handler: CallbackHandler):
    store.update_research_status(trip.trip_id, "running")
    await manager.broadcast(trip.trip_id, _research_status_message(store.get_trip(trip.trip_id)))

    state = {
        "destination": ", ".join(trip.destinations),
        "travel_date": trip.start_date,
        "search_queries": [],
        "web_research_result": [],
        "sources_gathered": [],
        "report": "",
    }
    config = {
        "configurable": {"thread_id": trip.trip_id},
        "callbacks": [langfuse_handler],
        "metadata": {"langfuse_session_id": trip.trip_id},
    }

    try:
        result = await research_workflow.ainvoke(state, config)
        store.update_research_status(trip.trip_id, "done", report=result["report"])
        logger.info("[run_research] done trip=%s", trip.trip_id)
    except Exception as e:
        store.update_research_status(trip.trip_id, "failed", error=str(e))
        logger.info("[run_research] failed trip=%s error=%s", trip.trip_id, e)

    await manager.broadcast(trip.trip_id, _research_status_message(store.get_trip(trip.trip_id)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.2)
    app.state.memory_store = MemoryStore()
    with SqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
        app.state.workflow = build_workflow(llm=llm, checkpointer=checkpointer)
        app.state.langfuse_handler = CallbackHandler()
        yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat", response_model=APIChatResponse)
async def chat(request: APIChatRequest, fastapi_request: Request):
    if request.user_message.startswith("/start"):
        store: MemoryStore = fastapi_request.app.state.memory_store
        trip = parse_start_command(
            request.user_message, trip_id=request.thread_id)
        if trip is None:
            msg = "usage: /start <name> | <destinations> | <date>  e.g. /start Georgia Trip | Tbilisi, Yerevan | June 2026"
            return APIChatResponse(thread_id=request.thread_id, langfuse_session_id=request.langfuse_session_id, chat_response=msg)
        trip = store.create_trip(trip)
        logger.info("[chat:/start] trip created id=%s name=%s", trip.trip_id, trip.name)
        asyncio.create_task(run_research(store, trip, fastapi_request.app.state.langfuse_handler))
        msg = f"Trip '{trip.name}' created. Destinations: {', '.join(trip.destinations)}. Date: {trip.start_date}. Researching now — connect to /ws/trip/{trip.trip_id} for status."
        return APIChatResponse(thread_id=request.thread_id, langfuse_session_id=request.langfuse_session_id, chat_response=msg)

    workflow = fastapi_request.app.state.workflow
    config = {
        "configurable": {"thread_id": request.thread_id},
        "callbacks": [app.state.langfuse_handler],
        "metadata": {"langfuse_session_id": request.langfuse_session_id}
    }
    logger.info("[chat] request thread=%s", request.thread_id)
    state = await asyncio.to_thread(
        workflow.invoke,
        {"messages": [HumanMessage(content=request.user_message)]},
        config,
    )

    if state.get("responses"):
        travel: TravelResponse = state["responses"][-1]
    else:
        travel = TravelResponse(chat_response=state["messages"][-1].content)

    return APIChatResponse(thread_id=request.thread_id, langfuse_session_id=request.langfuse_session_id, **travel.model_dump())


@app.websocket("/ws/trip/{trip_id}")
async def trip_status_ws(ws: WebSocket, trip_id: str):
    store: MemoryStore = ws.app.state.memory_store
    await manager.connect(trip_id, ws)
    trip = store.get_trip(trip_id)
    if trip is not None:
        await ws.send_json(_research_status_message(trip))
    else:
        await ws.send_json({"trip_id": trip_id, "status": "unknown", "report": None, "error": None})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(trip_id, ws)
