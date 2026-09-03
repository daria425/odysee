from langchain_core.messages import AIMessage
from app.agent.chat.graph import should_continue


def test_routes_to_format_response_when_no_tool_calls():
    state = {"messages": [AIMessage(content="Here is some info.")]}
    assert should_continue(state) == "format_response"


def test_routes_to_format_response_when_respond_tool_called():
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "respond", "type": "tool_call", "args": {}}],
            )
        ]
    }
    assert should_continue(state) == "format_response"


def test_routes_to_tool_node_when_other_tool_called():
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"id": "call_2", "name": "call_nightlife_agent", "type": "tool_call", "args": {}}],
            )
        ]
    }
    assert should_continue(state) == "tool_node"
