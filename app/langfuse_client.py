from langfuse import get_client
from dotenv  import load_dotenv
load_dotenv()  # Load environment variables from .env file
lf = get_client()
 
# Verify connection
def verify_connection():
    if lf.auth_check():
        print("Langfuse client is authenticated and ready!")
    else:
        print("Authentication failed. Please check your credentials and host.")