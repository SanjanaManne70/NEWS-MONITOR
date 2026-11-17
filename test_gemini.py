
import os
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY missing from .env")

# Initialize Gemini client
client = genai.Client(api_key=API_KEY)

MODEL = "gemini-3.5-flash-lite"
print("Connecting to Gemini...")

try:
    response = client.models.generate_content(
        model=MODEL,
        contents="""
        Return a JSON object with these fields:
        status: success
        purpose: natural language news database querying
        """
    )

    print("\nSUCCESS! Gemini API is responding.")
    print("Model:", MODEL)
    print("Response:")
    print(response.text)

except Exception as e:
    print("\nGEMINI CONNECTION FAILED")
    print("Error:", str(e))
