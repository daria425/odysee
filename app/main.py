from langfuse.langchain import CallbackHandler
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from app.graph import workflow
from uuid import uuid4
load_dotenv()  # Load environment variables from .env file
langfuse_handler = CallbackHandler()

if __name__ == "__main__":
    session_id = f"test-session-{str(uuid4())}"
    thread_id = f"test-thread-{str(uuid4())}"
    config = {
        "configurable": {"thread_id": thread_id},
        "callbacks": [langfuse_handler],
        "metadata": {"langfuse_session_id": session_id}
    }
    while True:
        user_input = input("User: ")
        if user_input in ("exit", "quit"):
            break
        state = workflow.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
        print("AI:", state["messages"][-1].content)
