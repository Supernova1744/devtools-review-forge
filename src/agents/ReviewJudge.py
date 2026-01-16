from typing import List, Dict, Any
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.utils import parse_rating, load_csv_data
from .base_agent import BaseAgent
from src.Models import ReviewVerdict

class ReviewJudge(BaseAgent):
    def __init__(self, model="xiaomi/mimo-v2-flash:free", temperature=0.0, csv_path="data/real_reviews_capterra.csv", rating_column="rating", persona="an expert Review Quality Judge", review_characteristics=None):
        super().__init__(model=model, temperature=temperature, csv_path=csv_path, rating_column=rating_column)
        self.persona = persona
        self.review_characteristics = review_characteristics or {}

    def evaluate_reviews(self, generated_reviews: List[Dict[str, Any]], target_rating: float):
        """
        Evaluates a list of generated reviews.
        """
        results = []
        for review in generated_reviews:
            review_text = f"General: {review.get('general', 'N/A')}\n"
            review_text += f"Pros: {review.get('pros', 'N/A')}\n"
            review_text += f"Cons: {review.get('cons', 'N/A')}"
            
            verdict = self.evaluate_single_review(review_text, target_rating)
            results.append({
                "review": review,
                "judgment": verdict
            })
        return results

    def evaluate_single_review(self, generated_review_text, target_rating):
        """
        Evaluates a single review text against real reviews of the same rating.
        """
        filtered_df = self.df[self.df[self.rating_column] == float(target_rating)]
        
        if filtered_df.empty:
            print(f"⚠️ No real reviews found for rating {target_rating} to compare against.")
            return {"verdict": "UNKNOWN", "reason": "No ground truth matches found."}

        sample_count = min(len(filtered_df), 10)
        samples = filtered_df.sample(n=sample_count)
        
        samples_text = ""
        for i, row in samples.iterrows():
            samples_text += f"[Real Review]\n"
            samples_text += f"General: {row.get('general', 'N/A')}\n"
            samples_text += f"Pros: {row.get('pros', 'N/A')}\n"
            samples_text += f"Cons: {row.get('cons', 'N/A')}\n"
            samples_text += "-" * 20 + "\n"
        
        # Prepare Characteristics Context
        characteristics_text = ""
        if self.review_characteristics:
            tones = self.review_characteristics.get('tones', [])
            focus_topics = self.review_characteristics.get('focus_topics', [])
            
            characteristics_text += "\nVALID GENERATION PARAMETERS (The review MAY use these styles/topics):\n"
            if tones:
                characteristics_text += f"- Acceptable Tones: {', '.join(tones)}\n"
            if focus_topics:
                characteristics_text += f"- Acceptable Topics: {', '.join(focus_topics)}\n"

        parser = JsonOutputParser(pydantic_object=ReviewVerdict)

        template = """
        You are {persona}. 
        Your task is to determine if a "Generated Review" looks and sounds like a REAL user review for Visual Studio Code, 
        specifically compared to the style, tone, length, and detail level of recent real reviews (provided below).

        Target Rating: {target_rating}
        
        {characteristics_text}

        REFERENCE REVIEWS (Ground Truth):
        {samples_text}

        GENERATED REVIEW TO EVALUATE:
        {generated_review}

        CRITERIA:
        1. Tone: Does it sound like a developer/user writing on Capterra? (Not too marketing-heavy, not too robotic).
        2. Realism: Does it mention specific VS Code features or issues consistent with valid feedback?
        3. Formatting: Does it loosely follow the General/Pros/Cons structure?

        Response must be in JSON format:
        {format_instructions}
        """

        prompt = PromptTemplate(
            input_variables=["target_rating", "samples_text", "generated_review", "characteristics_text"],
            template=template,
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        chain = prompt | self.llm | parser

        # print(f"⚖️ Judging review against {sample_count} real samples...")
        try:
            result = chain.invoke({
                "target_rating": target_rating,
                "samples_text": samples_text,
                "generated_review": generated_review_text,
                "persona": self.persona,
                "characteristics_text": characteristics_text
            })
            return result
        except Exception as e:
            print(f"❌ Judgment Error: {e}")
            return {"verdict": "ERROR", "reason": str(e)}

if __name__ == "__main__":
    try:
        judge = ReviewJudge()
        
        fake_reviews = [
            {
                "general": "It's the best editor I've used. Fast and reliable.",
                "pros": "Infinite extensions, great community, free.",
                "cons": "Sometimes uses too much RAM."
            },
            {
                "general": "I am an AI model. Visual Studio Code is a source-code editor made by Microsoft.",
                "pros": "It has features.",
                "cons": "None."
            }
        ]

        print("\n--- TEST: Evaluating Reviews (Rating 5.0) ---")
        results = judge.evaluate_reviews(fake_reviews, 5.0)
        
        import json
        print(json.dumps(results, indent=2))
        
    except Exception as e:
        print(f"Global Error: {e}")
