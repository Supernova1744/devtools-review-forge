from pydantic import BaseModel, Field

class Review(BaseModel):
    general: str = Field(description="The general text of the review")
    pros: str = Field(description="The pros mentions in the review")
    cons: str = Field(description="The cons mentions in the review")


