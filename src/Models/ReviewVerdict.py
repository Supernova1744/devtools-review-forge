from pydantic import BaseModel, Field

class ReviewVerdict(BaseModel):
    verdict: str = Field(description="The verdict of the evaluation, either 'PASS' or 'FAIL'")
    reason: str = Field(description="A brief explanation of why the review passed or failed, citing specific criteria like tone, style, or realism.")
