import asyncio
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langfuse.langchain import CallbackHandler
from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
from app.agent.chat.graph import build_workflow
from app.agent.research.graph import workflow as research_workflow
from app.lib.models import TravelResponse, APIChatResponse, APIChatRequest
from app.lib.db.models import Trip
from app.lib.db.store import DB_PATH, MemoryStore
from app.lib.report_ui import generate_report_ui, ReportUiGenerationError
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
        "type": "status",
        "trip_id": trip.trip_id,
        "status": trip.research_status,
        "report": trip.research_report,
        "report_ui": trip.research_report_ui,
        "error": trip.research_error,
        "research_started_at": trip.research_started_at,
        "research_updated_at": trip.research_updated_at,
    }


async def _generate_and_broadcast_sections(store: MemoryStore, trip_id: str, confirmed: list[dict], config: dict) -> None:
    """confirmed: list of {"id", "question", "answer"} for ids reflection just cleared this round.
    Generates each one's A2UI card concurrently (they're independent Haiku calls), but persists and
    broadcasts each one the instant it finishes rather than waiting for the whole round — retries
    on one card (up to 3 attempts) shouldn't delay every other card in the same round. Persist calls
    are still processed one at a time here (never concurrently), so there's no read-modify-write race
    against research_report_ui even though generation itself runs in parallel."""
    async def build_section(item: dict) -> dict | None:
        surface_id = f"{trip_id}-{item['id']}"
        section_md = f"## {item['question']}\n\n{item['answer']}"
        try:
            messages = await asyncio.to_thread(
                generate_report_ui, section_md, surface_id, config)
            return {"question_id": item["id"], "surface_id": surface_id, "messages": json.loads(messages)}
        except ReportUiGenerationError as e:
            logger.warning("[run_research] section report_ui generation failed trip=%s id=%s error=%s", trip_id, item["id"], e)
            return None

    for coro in asyncio.as_completed([build_section(item) for item in confirmed]):
        section = await coro
        if section is None:
            continue
        store.append_report_ui_sections(trip_id, [section])
        await manager.broadcast(trip_id, {"type": "section_ui", "trip_id": trip_id, **section})


async def run_research(store: MemoryStore, trip: Trip, langfuse_handler: CallbackHandler, should_generate_ui: bool = False):
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
        answers: dict[int, dict] = {}
        report: str | None = None
        async for update in research_workflow.astream(state, config, stream_mode="updates"):
            for node_name, node_output in update.items():
                if node_name == "web_research":
                    for item in node_output["web_research_result"]:
                        answers[item["id"]] = item
                elif node_name == "should_regenerate":
                    confirmed_ids = node_output.get("confirmed_ids") or []
                    if should_generate_ui and confirmed_ids:
                        confirmed = [answers[i] for i in confirmed_ids]
                        await _generate_and_broadcast_sections(store, trip.trip_id, confirmed, config)
                elif node_name == "finalize_answer":
                    report = node_output["report"]

        store.update_research_status(trip.trip_id, "done", report=report)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/trips", response_model=list[Trip])
async def list_trips(fastapi_request: Request):
    store: MemoryStore = fastapi_request.app.state.memory_store
    return store.list_trips()


@app.get("/trip/{trip_id}", response_model=Trip)
async def get_trip(trip_id: str, fastapi_request: Request):
    store: MemoryStore = fastapi_request.app.state.memory_store
    trip = store.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip not found")
    return trip


@app.get("/trip/{trip_id}/messages")
async def get_trip_messages(trip_id: str, fastapi_request: Request):
    workflow = fastapi_request.app.state.workflow
    config = {"configurable": {"thread_id": trip_id}}
    state = workflow.get_state(config)
    messages = state.values.get("messages", []) if state else []

    result = []
    for m in messages:
        if not isinstance(m, (HumanMessage, AIMessage)) or not isinstance(m.content, str) or not m.content:
            continue
        entry = {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
        if result and result[-1] == entry:
            continue
        result.append(entry)
    return result


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
        logger.info("[chat:/start] trip created id=%s name=%s",
                    trip.trip_id, trip.name)
        asyncio.create_task(run_research(
            store, trip, fastapi_request.app.state.langfuse_handler, should_generate_ui=True))
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
        await ws.send_json({"type": "status", "trip_id": trip_id, "status": "unknown", "report": None, "error": None})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(trip_id, ws)
