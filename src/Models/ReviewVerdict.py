from pydantic import BaseModel, Field

class ReviewVerdict(BaseModel):
    verdict: str = Field(description="The verdict of the evaluation, either 'PASS' or 'FAIL'")
    quality_score: int = Field(description="A quality score from 1-10 assessing realism, depth, and utility (1=Spam, 10=Perfect Realism).")
    reason: str = Field(description="A brief explanation of why the review passed or failed, citing specific criteria like tone, style, or realism.")
