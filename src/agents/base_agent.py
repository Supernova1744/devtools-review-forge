import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src.utils import parse_rating, load_csv_data

load_dotenv()

class BaseAgent:
    def __init__(self, model="xiaomi/mimo-v2-flash:free", temperature=0.7, csv_path="data/real_reviews_capterra.csv", rating_column="rating"):
        self.model = model
        self.temperature = temperature
        self.rating_column = rating_column
        self.df = load_csv_data(csv_path)

        if self.rating_column in self.df.columns:
            self.df[self.rating_column] = self.df[self.rating_column].apply(parse_rating)
            self.df = self.df.dropna(subset=[self.rating_column])
        else:
            raise ValueError(f"❌ Error: '{self.rating_column}' column not found in CSV file.")
        
        if self.df.empty:
            raise ValueError("❌ Error: DataFrame is empty.")

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
