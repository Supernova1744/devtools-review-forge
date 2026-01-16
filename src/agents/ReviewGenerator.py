import os
import pandas as pd
import random
from typing import List
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from .base_agent import BaseAgent
from src.Models import Review, ReviewList

from src.utils import parse_rating, load_csv_data

class ReviewGenerator(BaseAgent):
    def __init__(self, model="xiaomi/mimo-v2-flash:free", rollback_model=None, temperature=0.7, csv_path="data/real_reviews_capterra.csv", rating_column="rating", persona="a Technical Reviewer", review_characteristics=None):
        super().__init__(model=model, rollback_model=rollback_model, temperature=temperature, csv_path=csv_path, rating_column=rating_column)
        self.persona = persona
        self.review_characteristics = review_characteristics or {}

    def generate_reviews(self, target_rating, count=5):
        """
        Generates fake reviews based on the style of existing reviews with the target rating.
        """
        # Filter by rating
        filtered_df = self.df[self.df[self.rating_column] == float(target_rating)]

        if filtered_df.empty:
            print(f"ℹ️ No reviews found with rating '{target_rating}'. Cannot generate samples.")
            return

        # Select random samples
        sample_count = min(len(filtered_df), 5)
        samples = filtered_df.sample(n=sample_count)
        
        print(f"✅ Found {len(filtered_df)} reviews with rating {target_rating}. Using {sample_count} samples for style transfer.")

        # formatting samples for the prompt
        samples_text = ""
        for i, row in samples.iterrows():
            samples_text += f"Review {i+1}:\n"
            samples_text += f"General: {row.get('general', 'N/A')}\n"
            samples_text += f"Pros: {row.get('pros', 'N/A')}\n"
            samples_text += f"Cons: {row.get('cons', 'N/A')}\n"
            samples_text += "-" * 20 + "\n"
        
        # Prepare Characteristics Context
        characteristics_text = ""
        if self.review_characteristics:
            tones = self.review_characteristics.get('tones', [])
            focus_topics = self.review_characteristics.get('focus_topics', [])
            
            characteristics_text += "\nREVIEW CHARACTERISTICS TO APPLY:\n"
            if tones:
                characteristics_text += f"- Available Tones: {', '.join(tones)} (Select diverse tones from this list)\n"
            if focus_topics:
                characteristics_text += f"- Focus Topics to Mention: {', '.join(focus_topics)} (Randomly incorporate these)\n"

        # Define the Parser
        parser = JsonOutputParser(pydantic_object=ReviewList)

        # Define the Prompt
        template = """
        You are {persona} tasked with generating realistic user reviews for Visual Studio Code (VS Code).
        Your goal is to create {count} new, unique reviews that mimic the style, tone, and length of the provided examples.
        
        Target Rating: {target_rating} / 5.0
        
        {characteristics_text}
        
        Here are {sample_count} real examples of reviews with this rating:
        {samples_text}
        
        Output Format:
        {format_instructions}
        
        Ensure the content is diverse but plausible for a VS Code user giving this specific rating.
        """

        prompt = PromptTemplate(
            input_variables=["count", "target_rating", "sample_count", "samples_text", "characteristics_text"],
            template=template,
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        chain = prompt | self.llm | parser

        print("🧠 Generating reviews using LLM (JSON Output)...")
        try:
            result = chain.invoke({
                "count": count,
                "target_rating": target_rating,
                "sample_count": sample_count,
                "samples_text": samples_text,
                "persona": self.persona,
                "characteristics_text": characteristics_text
            })
            
            print("\n" + "="*40)
            print("✨ GENERATED REVIEWS ✨")
            print("="*40)
            print(result)
            return result

        except Exception as e:
            print(f"❌ Error generating reviews with primary model: {e}")
            if self.rollback_llm:
                print(f"🔄 Attempting rollback with model: {self.rollback_model}")
                try:
                    chain_rollback = prompt | self.rollback_llm | parser
                    result = chain_rollback.invoke({
                        "count": count,
                        "target_rating": target_rating,
                        "sample_count": sample_count,
                        "samples_text": samples_text,
                        "persona": self.persona,
                        "characteristics_text": characteristics_text
                    })
                    print("\n" + "="*40)
                    print("✨ GENERATED REVIEWS (ROLLBACK) ✨")
                    print("="*40)
                    print(result)
                    return result
                except Exception as rollback_e:
                     print(f"❌ Rollback failed as well: {rollback_e}")
            else:
                 print("⚠️ No rollback model configured.")

if __name__ == "__main__":
    generator = ReviewGenerator()
    
    print("\n--- Testing Generation for 5.0 Rating ---")
    generator.generate_reviews(target_rating=5.0, count=3)
    
    print("\n--- Testing Generation for 3.0 Rating ---")
    generator.generate_reviews(target_rating=3.0, count=2)
