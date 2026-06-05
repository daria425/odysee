from langchain_core.messages import SystemMessage, AIMessage
from app.lib.utils import load_prompt
from app.lib.models import TravelResponse

MESSAGE_WINDOW = 10


def trimmer(messages: list, trim_window: int) -> list:
    return messages[-trim_window:]


def trim_messages(state):
    return {"messages": trimmer(state["messages"], MESSAGE_WINDOW)}


def make_chatbot(chat_llm, profile):
    def chatbot(state):
        system_prompt = load_prompt(
            "app/lib/prompts/chat_prompt.txt", user_profile=profile)
        response: TravelResponse = chat_llm.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"])
        return {
            "messages": [AIMessage(content=response.chat_response)],
            "responses": state.get("responses", []) + [response],
        }
    return chatbot
