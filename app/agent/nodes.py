import json
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from app.lib.utils import load_prompt
from app.lib.models import TravelResponse
from app.agent.tools import make_nightlife_agent_tool

MESSAGE_WINDOW = 10


def trimmer(messages: list, trim_window: int) -> list:
    return messages[-trim_window:]


def trim_messages(state):
    return {"messages": trimmer(state["messages"], MESSAGE_WINDOW)}


def make_chatbot(llm, profile):
    nightlife_prompt = load_prompt("app/lib/prompts/nightlife_research_prompt.txt", user_profile=profile)
    nightlife_tool = make_nightlife_agent_tool(llm, nightlife_prompt)

    respond_tool = StructuredTool.from_function(
        func=lambda **kwargs: TravelResponse(**kwargs),
        name="respond",
        description="Use this to give your final answer to the user.",
        args_schema=TravelResponse,
    )

    chat_llm = llm.bind_tools([nightlife_tool, respond_tool])
    tools_by_name = {
        "call_nightlife_agent": nightlife_tool,
        "respond": respond_tool,
    }

    def chatbot(state):
        system_prompt = load_prompt("app/lib/prompts/chat_prompt.txt", user_profile=profile)
        messages = [SystemMessage(content=system_prompt)] + state["messages"]

        while True:
            response = chat_llm.invoke(messages)
            messages.append(response)

            for tool_call in response.tool_calls:
                if tool_call["name"] == "respond":
                    final = TravelResponse(**tool_call["args"])
                    return {
                        "messages": [AIMessage(content=final.chat_response)],
                        "responses": state.get("responses", []) + [final],
                    }
                result = tools_by_name[tool_call["name"]].invoke(tool_call["args"])
                messages.append(
                    ToolMessage(content=json.dumps(result), tool_call_id=tool_call["id"])
                )

    return chatbot
