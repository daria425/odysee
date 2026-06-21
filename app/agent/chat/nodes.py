import logging
import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from app.lib.models import TravelResponse, MemoryExtractionResult
from app.lib.utils import load_prompt
from app.lib.db.store import MemoryStore
from app.lib.db.models import TripMemoryLogEntry

logger = logging.getLogger(__name__)

MESSAGE_WINDOW = 10


def trimmer(messages: list, trim_window: int) -> list:
    return messages[-trim_window:]


def trim_messages(state):
    return {"messages": trimmer(state["messages"], MESSAGE_WINDOW)}


def format_response(state):
    last = state["messages"][-1]
    if last.tool_calls and last.tool_calls[0]["name"] == "respond":
        tool_call = last.tool_calls[0]
        final = TravelResponse(**tool_call["args"])
        extra_messages = [
            ToolMessage(content="ok", tool_call_id=tool_call["id"]),
            AIMessage(content=final.chat_response),
        ]
        logger.info("format_response: structured respond tool")
    else:
        final = TravelResponse(chat_response=last.content)
        extra_messages = []
        logger.info("format_response: plain text fallback")
    return {
        "messages": extra_messages,
        "responses": state.get("responses", []) + [final],
    }


def make_log_memory(store: MemoryStore):
    def log_memory(state, config: RunnableConfig):
        trip_id = config["configurable"]["thread_id"]
        if store.get_trip(trip_id) is None:
            return {}

        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        if last_human is None:
            return {}

        llm = ChatAnthropic(
            model_name="claude-haiku-4-5-20251001", temperature=0,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        ).with_structured_output(MemoryExtractionResult)
        system_prompt = load_prompt("app/lib/prompts/log_memory_prompt.txt")
        response: MemoryExtractionResult = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=last_human.content)]
        )

        if response.memory_entry:
            store.add_memory_entry(TripMemoryLogEntry(trip_id=trip_id, content=response.memory_entry))
            logger.info("log_memory: stored '%s' for trip %s", response.memory_entry, trip_id)

        return {}

    return log_memory


def make_call_model(llm, profile, chatbot_tools=None):
    chat_llm = llm.bind_tools(chatbot_tools or [])

    def call_model(state):
        system_prompt = load_prompt("app/lib/prompts/chat_prompt.txt", user_profile=profile)
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = chat_llm.invoke(messages)
        return {"messages": [response]}

    return call_model
