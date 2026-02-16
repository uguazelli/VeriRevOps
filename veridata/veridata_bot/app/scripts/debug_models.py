import os
import google.generativeai as genai
from app.core.config import settings

def list_models():
    genai.configure(api_key=settings.google_api_key)
    print("Listing available models that support embeddings or generation...")
    try:
        found_embedding = False
        for m in genai.list_models():
            methods = m.supported_generation_methods
            if 'embedContent' in methods:
                print(f"  [EMBEDDING] {m.name}")
                found_embedding = True
            elif 'generateContent' in methods:
                # Optional: list generation models too just in case
                # print(f"  [GENERATION] {m.name}")
                pass

        if not found_embedding:
            print("No embedding models found for this API key.")

    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
