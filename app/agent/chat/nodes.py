from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from app.lib.models import TravelResponse
from app.lib.utils import load_prompt

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
    else:
        final = TravelResponse(chat_response=last.content)
        extra_messages = []
    return {
        "messages": extra_messages,
        "responses": state.get("responses", []) + [final],
    }


def make_call_model(llm, profile, chatbot_tools=None):
    chat_llm = llm.bind_tools(chatbot_tools or [])

    def call_model(state):
        system_prompt = load_prompt("app/lib/prompts/chat_prompt.txt", user_profile=profile)
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = chat_llm.invoke(messages)
        return {"messages": [response]}

    return call_model
