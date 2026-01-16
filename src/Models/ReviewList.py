from pydantic import BaseModel, Field
from typing import List
from .Review import Review

class ReviewList(BaseModel):
    reviews: List[Review] = Field(description="A list of generated reviews")