from langfuse.langchain import CallbackHandler
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from app.graph import workflow
load_dotenv()  # Load environment variables from .env file
langfuse_handler = CallbackHandler()

if __name__=="__main__":
    initial_state = {
        "messages": [],
        "responses": []
    }
    while True:
        user_input = input("User: ")
        if user_input in ("exit", "quit"):
            break
        initial_state["messages"].append(HumanMessage(content=user_input))
        state = workflow.invoke({"messages": initial_state["messages"]},
                                config={"callbacks": [langfuse_handler]})
        initial_state["messages"] = state["messages"]
        print("AI:", state["messages"][-1].content)