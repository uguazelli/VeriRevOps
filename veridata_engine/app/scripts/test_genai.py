import os
from dotenv import load_dotenv
from google import genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not found")
    exit(1)

print("--- Testing google-genai SDK ---")
client = genai.Client(api_key=api_key)
try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hello from SDK"
    )
    print(f"✅ SDK test successful: {response.text[:50]}...")
except Exception as e:
    print(f"❌ SDK test failed: {e}")

print("\n--- Testing langchain-google-genai ---")
try:
    chat = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key
    )
    response = chat.invoke([HumanMessage(content="Hello from LangChain")])
    print(f"✅ LangChain test successful: {response.content[:50]}...")
except Exception as e:
    print(f"❌ LangChain test failed: {e}")
