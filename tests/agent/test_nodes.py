from app.agent.nodes import trimmer, make_call_model
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage


def test_trims_when_over_window():
    messages = list(range(15))
    assert trimmer(messages, 10) == list(range(5, 15))


def test_returns_all_when_under_window():
    messages = list(range(5))
    assert trimmer(messages, 10) == list(range(5))


def test_returns_all_when_exactly_window():
    messages = list(range(10))
    assert trimmer(messages, 10) == list(range(10))


def test_empty_messages():
    assert trimmer([], 10) == []


def test_call_model_adds_response():
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(content="Here's some info")

    call_model = make_call_model(mock_llm, "", [])
    mock_state = {"messages": [HumanMessage(
        content="What's some nice coffee shops around Vera?")]}
    res = call_model(mock_state)
    assert len(res["messages"]) == 1
    assert res["messages"][0].content == "Here's some info"


def test_call_model_adds_tool_calls():
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.invoke.return_value = AIMessage(
        content="",
        tool_calls=[{
            "id": "call_abc",
            "name": "respond",
            "type": "tool_call",
            "args": {
                "chat_response": "Here are some places.",
                "recommendations": [""],
                "warnings": [],
                "follow_up": []
            }
        }]
    )
    call_model = make_call_model(mock_llm, "", [])
    mock_state = {"messages": [HumanMessage(
        content="What's some nice coffee shops around Vera?")]}
    res = call_model(mock_state)
    assert res["messages"][0].tool_calls[0]["name"] == "respond"
