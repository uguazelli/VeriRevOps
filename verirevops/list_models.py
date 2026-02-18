from google import genai
import os

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("GOOGLE_API_KEY not found in environment.")
    exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("Listing available embedding models...")
    models = client.models.list()

    found = False
    for m in models:
        # Check if 'embed' is in the name (case insensitive)
        if "embed" in m.name.lower():
            print(f"Model Name: {m.name}")
            try:
                print(f"Display Name: {m.display_name}")
            except:
                pass
            print("-" * 20)
            found = True

    if not found:
        print("No models found with 'embed' in the name.")

except Exception as e:
    print(f"Error listing models: {e}")
