from langfuse.langchain import CallbackHandler
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from app.graph import workflow
load_dotenv()  # Load environment variables from .env file
langfuse_handler = CallbackHandler()

if __name__=="__main__":
    while True:
      user_input = input("User: ")
      if user_input in ("exit", "quit"):
          break
      state = workflow.invoke({"messages": [HumanMessage(content=user_input)]}, 
                              config={"callbacks": [langfuse_handler]})
      print("AI:", state["messages"][-1].content)