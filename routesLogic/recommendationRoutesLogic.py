from core import recommednations
from dtos.recommendation_fetch_dto import RecommendationFetchDTO
import asyncio

async def generate_recommendations(recommendation_fetch_data: RecommendationFetchDTO):
    """
    Fetch recommendations based on the provided DTO.
    
    Args:
        recommendation_fetch_dto (RecommendationFetchDTO): The data transfer object containing the request parameters.
    
    Returns:
        dict: A dictionary containing the recommendations and metadata.
    """
    details = {
        'session_id': recommendation_fetch_data.session_id,
        'recommendation_category': recommendation_fetch_data.selected_category,
        'user_message': recommendation_fetch_data.user_message,
        'selected_tag_id': recommendation_fetch_data.selected_tag_id,
        'is_tags_only': recommendation_fetch_data.is_tags_only,
        'tag_id': recommendation_fetch_data.selected_tag_id
    }
    recommendations, is_processing, error_message = await recommednations.get_recommendations_by_details(details, page=1)
    if (not recommendations) and (is_processing == False or is_processing is None):
        asyncio.create_task(recommednations.generate_alonis_qloo_powered_recommendations(
            recommendation_fetch_data.session_id,
            recommendation_fetch_data.selected_category,
            recommendation_fetch_data.user_message,
            recommendation_fetch_data.is_tags_only,
            recommendation_fetch_data.selected_tag_id
        ))
        print("Recommendation generation task started in the background.")

    recommendations = await get_recommendations_by_details(details=details, page=1)
    return recommendations

async def get_recommendations_by_details(details: dict, page=1):
    """
    Fetch recommendations based on the provided details.
    
    Args:
        details (dict): A dictionary containing the details to filter recommendations.
    
    Returns:
        list: A list of recommendations based on the provided details.
    """
    recommendations, is_processing, error_message = None, True, None
    trials = 0
    while not recommendations:
        recommendations, is_processing, error_message = await recommednations.get_recommendations_by_details(details, page=page)
        if trials >= 3:
            # Confirm is processing status is True to keep waiting else break
            if not is_processing:
                break
        if not recommendations:
            # If no recommendations found, wait for a while before retrying
            await asyncio.sleep(2)
        trials += 1

    if not recommendations:
        return {"recommendations": {}, "status_code": 404, "error": error_message}
    
    return {
        "recommendations": recommendations,
        "status_code": 200
    }