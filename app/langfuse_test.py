from langfuse import get_client
from dotenv  import load_dotenv
load_dotenv()  # Load environment variables from .env file
langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")