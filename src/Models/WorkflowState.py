
from typing import TypedDict, List, Dict, Any, Annotated
import operator

class WorkflowState(TypedDict):
    target_rating: float
    required_count: int
    accepted_reviews: Annotated[List[Dict[str, Any]], operator.add]
    current_generated_reviews: List[Dict[str, Any]]
    cumulative_generated: Annotated[int, operator.add]
    current_judgments: List[Dict[str, Any]]
    iteration: int