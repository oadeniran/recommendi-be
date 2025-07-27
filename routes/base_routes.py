from fastapi import APIRouter
from dtos.recommendation_fetch_dto import RecommendationFetchDTO
from routesLogic import recommendationRoutesLogic
import asyncio

ENTITIES_FORMATTED = {
    "Movies": "movies",
    "TV Shows": "tv_shows",
    'Books': 'books',
    'Destinations': 'destinations',
    'Places': 'places',
}

CATEGORIES_DATA = [
    {
        "name": "Movies",
        "value": "Movies",
        "label": "Tell us what kind of movie recommendations you are looking for",
        "placeholder": "e.g., 'I just saw Romeo and Juliet, can you recommmend more movies like this..'",
    },
    {
        "name": "Books",
        "value": "Books",
        "label": "Tell us what kind of book recommendations you are looking for",
        "placeholder": "e.g., 'I just read The Great Gatsby, can you recommmend more books like this..'",
    },
    {
        "name": "Places",
        "value": "Places",
        "label": "Tell us what kind of place recommendations you are looking for",
        "placeholder": "e.g., 'I am looking for good restaurants in New York, can you recommmend some places..'",
    },
    {
        "name": "TV Shows",
        "value": "TV Shows",
        "label": "Tell us what kind of TV show recommendations you are looking for",
        "placeholder": "e.g., 'I just saw Breaking Bad, can you recommmend more shows like this..'",
    },
    # {
    #     "name": "Destinations",
    #     "value": "Destinations",
    #     "label": "Tell us what kind of travel destination recommendations you are looking for",
    #     "placeholder": "e.g., 'I am planning a trip to Europe, can you recommmend some destinations..'",
    # },

]

router = APIRouter()

@router.get("/available-entities", tags=["Recommendi APIs"])
async def get_available_entities():
    """
    Get the list of available entities for recommendations.
    """
    return {
        "categories_data": CATEGORIES_DATA,
        'status_code': 200,
    }

@router.post("/recommendations", tags=["Recommendi APIs"])
async def generate_recommendations(recommendation_fetch_dto: RecommendationFetchDTO):
    """
    Fetch recommendations based on the provided DTO.
    
    Args:
        recommendation_fetch_dto (RecommendationFetchDTO): The data transfer object containing the request parameters.
    
    Returns:
        dict: A dictionary containing the recommendations and metadata.
    """
    if not recommendation_fetch_dto.session_id:
        return {"message": "Session ID is required", "status_code": 400}
    if not recommendation_fetch_dto.selected_category:
        return {"message": "Selected category is required", "status_code": 400}
    
    if recommendation_fetch_dto.selected_category not in ENTITIES_FORMATTED:
        return {"message": "Invalid category selected", "status_code": 400}
    else:
        recommendation_fetch_dto.selected_category = ENTITIES_FORMATTED[recommendation_fetch_dto.selected_category]

    recommendations = await recommendationRoutesLogic.generate_recommendations(recommendation_fetch_dto)

    return recommendations

@router.get("/recommendations/{session_id}/details", tags=["Recommendi APIs"])
async def get_recommendations_by_details(session_id: str, recommendation_category: str, user_message: str = None, selected_tag_id: str = None, page: int = 1):
    """
    Fetch recommendations based on the provided details.
    Args:
        details (dict): A dictionary containing the details to filter recommendations.
    Returns:
        dict: A dictionary containing the recommendations and metadata.
    """
    if not session_id:
        return {"message": "Session ID is required", "status_code": 400}
    if not recommendation_category:
        return {"message": "Recommendation category is required", "status_code": 400}
    if recommendation_category not in ENTITIES_FORMATTED:
        return {"message": "Invalid recommendation category", "status_code": 400}
    print(f"Fetching recommendations for session {session_id} in category {recommendation_category} with user message: {user_message} and selected tag ID: {selected_tag_id}")
    recommendations =  await recommendationRoutesLogic.get_recommendations_by_details({
        'session_id': session_id,
        'recommendation_category': ENTITIES_FORMATTED[recommendation_category],
        'user_message': user_message,
        'tag_id': selected_tag_id
    }, page=page)

    return recommendations