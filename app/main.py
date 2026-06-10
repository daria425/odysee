from langfuse.langchain import CallbackHandler
from langchain_core.messages import HumanMessage
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
from app.agent.chat.graph import build_workflow
from app.agent.chat.state import State
from uuid import uuid4

if __name__ == "__main__":
    load_dotenv()
    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.2)
    langfuse_handler = CallbackHandler()

    session_id = f"test-session-{str(uuid4())}"
    thread_id = f"test-thread-{str(uuid4())}"
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [langfuse_handler],
        "metadata": {"langfuse_session_id": session_id}
    }
    workflow = build_workflow(llm=llm)
    while True:
        user_input = input("User: ")
        if user_input in ("exit", "quit"):
            break
        state = workflow.invoke(State(messages=[HumanMessage(content=user_input)], responses=[]), config=config)
        print("AI:", state["messages"][-1].content)
