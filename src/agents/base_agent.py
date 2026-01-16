import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

class BaseAgent:
    def __init__(self, model="xiaomi/mimo-v2-flash:free", temperature=0.0):
        self.model = model
        self.temperature = temperature
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = None
        
        if not api_key:
            api_key = os.getenv("OPENROUTER_API_KEY")
            if api_key:
                print("ℹ️ Judge using OpenRouter API Key.")
                base_url = "https://openrouter.ai/api/v1"
            else:
                print("❌ Error: neither OPENAI_API_KEY nor OPENROUTER_API_KEY found.")
                self.llm = None
                return

        self.llm = ChatOpenAI(
            model=self.model, 
            temperature=self.temperature, # Lower temperature for evaluation
            api_key=api_key,
            base_url=base_url
        )
