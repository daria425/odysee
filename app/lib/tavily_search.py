from tavily import TavilyClient
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.environ.get("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key)
