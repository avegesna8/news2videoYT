from typing import List
from pydantic import BaseModel, Field

#Response Model for Top 3 Headlines Selection
class TopHeadlinesResponse(BaseModel):
    selected_indices: List[int] = Field(
        description="List of 3 indices (1-based) representing the most important headlines",
        min_length=3,
        max_length=3
    )
