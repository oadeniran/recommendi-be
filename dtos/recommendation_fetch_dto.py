from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class RecommendationFetchDTO(BaseModel):
    """
    Data Transfer Object for fetching recommendations.
    """
    session_id: str = Field(..., description="Unique identifier for the user session")
    selected_category: str = Field(..., description="Category of recommendations to fetch")
    user_message: Optional[str] = Field(None, description="User's message or query related to the recommendation")
    is_tags_only: bool = Field(False, description="Flag to indicate if only tags are requested")
    selected_tag_id: Optional[str] = Field(None, description="ID of the selected tag for tag based recommendations")