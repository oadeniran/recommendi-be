from core import qloo_core, llm_core
import asyncio
import random
from utils import dict_to_string, get_all_location_details, clean_text
from db import add_recommendation, get_recommendations_using_details, set_session_status_field, get_session_status_field
from traceback import format_exc

async def generate_alonis_qloo_powered_recommendations(session_id, recommendation_category = "Movies", user_message=None, is_tags_only=False, selected_tag_id=None):
    """
    Get Alonis recommendations powered by Qloo based on user preferences.
    """
    
    recommendations = None
    
    # Use Qloo API to get recommendations based on tags and current page
    # Use model to add a context on how the recommendation is a good fit for the user
    print(f"Generating recommendations for session {session_id} in category {recommendation_category} with user message: {user_message} and is_tags_only: {is_tags_only} and selected_tag_id: {selected_tag_id}")

    processing_status = await asyncio.to_thread(get_session_status_field,
        session_id,
        recommendation_category,
        user_message,
        selected_tag_id,
        field_key='is_processing'
    )
    print(f"Processing status for session {session_id}: {processing_status}")
    if processing_status and processing_status is True:
        return
    
    # Set the session processing status to True
    asyncio.create_task(asyncio.to_thread(set_session_status_field,
        session_id,
        recommendation_category,
        user_message,
        selected_tag_id,
        field_key='is_processing',
        field_value=True
    )
    )
    recommendations = None
    message_converted_to_tag = False
    last_location_details = None
    should_be_recent = False
    try:
        if is_tags_only == False:

            # Get recommendation data from user message
            # Try if we have it in the session data first
            recommendation_fetch_data = await asyncio.to_thread(get_session_status_field,
                session_id,
                recommendation_category,
                user_message,
                selected_tag_id,
                field_key='recommendation_fetch_details'
            )
            if not recommendation_fetch_data:
                # If not found, then we can use the LLM to get the recommendation data from the user message
                print(f"Recommendation fetch data not found in session data for session {session_id}, using LLM to get it from user message.")
                recommendation_fetch_data_for_user_message = await llm_core.get_recommendation_data_from_user_message(
                    user_message, 
                    recommendation_category, 
                )
            else:
                recommendation_fetch_data_for_user_message = recommendation_fetch_data
            print(f"Recommendation fetch data for user message: {recommendation_fetch_data_for_user_message}")

            if not recommendation_fetch_data_for_user_message or recommendation_fetch_data_for_user_message.get('is_valid', False) == False:
                raise Exception("show_user: Your message does not seem to be a valid one for generating recommendations. Please try again with a valid message.")
            
            if 'location' in recommendation_fetch_data_for_user_message and recommendation_fetch_data_for_user_message['location'] != '':
                # If the location is provided, get the location details
                location_detils = await asyncio.to_thread(get_all_location_details, recommendation_fetch_data_for_user_message['location'], country_level=qloo_core.is_country_level(recommendation_category))
                recommendation_fetch_data_for_user_message['location_details'] = location_detils
                # To enable us get last location details for a session, we can set the location details in the session data
                asyncio.create_task(asyncio.to_thread(set_session_status_field,
                    session_id,
                    recommendation_category,
                    None,
                    None,
                    field_key='last_location_details',
                    field_value=recommendation_fetch_data_for_user_message.get('location_details', {})
                ))
            
            # Update the session data with the recommendation fetch data
            asyncio.create_task(asyncio.to_thread(set_session_status_field,
                session_id,
                recommendation_category,
                user_message,
                selected_tag_id,
                field_key='recommendation_fetch_details',
                field_value=recommendation_fetch_data_for_user_message
            ))

            #Page tracking
            page_to_use = 1
            current_page = await asyncio.to_thread(get_session_status_field,
                                                session_id,
                                                recommendation_category,
                                                user_message,
                                                selected_tag_id,
                                                field_key='page')
            if current_page:
                page_to_use = current_page + 1
            
            
            # 3rd get recommendations from Qloo API based on the data
            if recommendation_fetch_data_for_user_message.get('is_specific', False) == True:
                recommendations = await asyncio.to_thread(qloo_core.get_qloo_search_recommendations,
                    recommendation_category, 
                    recommendation_fetch_data_for_user_message, 
                    page=page_to_use
                    )

                #Update page tracking for this message in the database
                asyncio.create_task(asyncio.to_thread(set_session_status_field,
                    session_id,
                    recommendation_category,
                    user_message,
                    selected_tag_id,
                    field_key='page',
                    field_value=page_to_use))
            else:
                message_converted_to_tag = True
                # If the message is not specific, we can use the generic term to get a tag to use for recommendations
                tag_to_use = await asyncio.to_thread(qloo_core.get_qloo_tag_to_use_for_non_specific,
                    recommendation_category, 
                    recommendation_fetch_data_for_user_message.get('generic_term', None),
                    backups=recommendation_fetch_data_for_user_message.get('backup_keywords', None)
                )
                print(f"Tag to use for non-specific message: {tag_to_use}")
                if tag_to_use:
                    selected_tag_id = tag_to_use
                last_location_details = recommendation_fetch_data_for_user_message.get('location_details', {})
                should_be_recent = recommendation_fetch_data_for_user_message.get('should_be_recent', False)
                asyncio.create_task(asyncio.to_thread(set_session_status_field,
                    session_id,
                    recommendation_category,
                    user_message,
                    None,
                    field_key='tag_switched_id',
                    field_value=selected_tag_id
                ))
                
        if recommendations is None or recommendations == {} and selected_tag_id is not None:
            # If only tags are selected, then its possible there is a last location details that can be used
            # If its a conversion from a message to a tag, we can use the last location details that was aved there so it will not be None,
            # If its not, we only need to add location details if the recommendation category is not country level as country level is used to denote those categories that ideally do not need country unless specified (movies, books) so the opposite of that is what we need to check
            if last_location_details is None and qloo_core.is_country_level(recommendation_category) == False:
                # Get the last location details from the session data
                last_location_details = await asyncio.to_thread(get_session_status_field,
                    session_id,
                    recommendation_category,
                    None,
                    None,
                    field_key='last_location_details'
                )
            print(f"Last location details for session {session_id}: {last_location_details}")
            page_to_use = 1
            current_page = await asyncio.to_thread(get_session_status_field,
                                                session_id,
                                                recommendation_category,
                                                user_message,
                                                selected_tag_id,
                                                field_key='page')
            if current_page:
                page_to_use = current_page + 1
            recommendations = await asyncio.to_thread(qloo_core.get_qloo_recommendations_by_tag_id, 
                                                    recommendation_category, 
                                                    selected_tag_id,
                                                    page=page_to_use,
                                                    location = last_location_details if last_location_details else None,
                                                    should_be_recent=should_be_recent
                                                    )
            asyncio.create_task(asyncio.to_thread(set_session_status_field,
                session_id,
                recommendation_category,
                user_message,
                selected_tag_id,
                field_key='page',
                field_value=page_to_use
            ))
        
        if recommendations is not None and recommendations != []:
            asyncio.create_task(enrich_and_save_recommendations(
                session_id = session_id, 
                user_query = user_message, 
                rec_category = recommendation_category, 
                recommendations = recommendations,
                tag_id = selected_tag_id,
                pseudo_query = f"The user is looking for recommendations based on the selected tag - {selected_tag_id or 'None'}",
                message_converted_to_tag = message_converted_to_tag
            ))
        else:
            print(f"No recommendations found for session {session_id} in category {recommendation_category} with user message: {user_message} and selected tag ID: {selected_tag_id}")
            raise Exception("show_user: No recommendations found for the given criteria. Please try again with different Message or Tag")
    except Exception as e:
        print(f"Error generating recommendations: {e}")
        asyncio.create_task(asyncio.to_thread(set_session_status_field,
            session_id,
            recommendation_category,
            user_message,
            None if message_converted_to_tag else selected_tag_id,
            field_key='is_processing',
            field_value=False
        ))

        if message_converted_to_tag:
        # We need to also stop the processing of the session for this tag
            asyncio.create_task(asyncio.to_thread(set_session_status_field,
                session_id,
                recommendation_category,
                None,
                selected_tag_id,
                field_key='is_processing',
                field_value=False
            ))

        # Add the error to error field of the session 
        if 'show_user' in str(e):
            # If the error has 'show_user' in it, we can set the error message to be shown to the user
            asyncio.create_task(asyncio.to_thread(set_session_status_field,
                session_id,
                recommendation_category,
                user_message,
                selected_tag_id,
                field_key='error_message',
                field_value=str(e).replace('show_user: ', '')
            ))
        else:
            # If the error does not have 'show_user' in it, then its a techinal one to set to technical_error field
            asyncio.create_task(asyncio.to_thread(set_session_status_field,
                session_id,
                recommendation_category,
                user_message,
                selected_tag_id,
                field_key='technical_error',
                field_value=str(e)
            ))
        print(f"Error generating recommendations: {format_exc()}")

async def enrich_and_save_recommendations(session_id, rec_category,recommendations, user_query = None, tag_id = None, pseudo_query=None, message_converted_to_tag=False):
    """
    Enrich the recommendations with additional data and save them to the database.
    """
    original_query = user_query
    if message_converted_to_tag:
            pseudo_query = f"""
             The user had initially asked for recommendations based on the following message: {user_query or 'None'}.
             But the system converted it to a tag based recommendation with tag ID: {tag_id or 'None'}. since the user did not provide a specific request, we are using the tag ID to generate recommendations.
            """
            original_query = user_query
            user_query = None
    # Get the model to generate context for the recommendations
    def enrich_recommendation(rec):
        # copy the recommendation to avoid modifying the original
        try:
            rec_ = rec.copy()
            if 'error' not in rec_:
                rec_['tags_original'] = None
                context_and_score = llm_core.get_context_and_score_for_recommndation_text(
                    rec_, user_message=user_query or pseudo_query
                )
                if not context_and_score:
                    print(f"No context and score found for recommendation {rec.get('title', 'Unknown')}")
                    return None
                context_text = context_and_score.get('context', '')
                score = context_and_score.get('score', 0)
                if score > 5:
                    rec['context'] = context_text
                    rec['extra_data_string'] = dict_to_string(rec.get('extra_data', {}), normalize_text=True)
            
                    # Now save the recommendation to the database
                    add_recommendation(
                        {
                            **rec,
                            'session_id': session_id,
                            'user_message': original_query,
                            'cleaned_user_message': clean_text(original_query),
                            'recommendation_category': rec_category,
                            'tag_id': tag_id,
                        }
                    )
                    print(f"Recommendation saved: {rec['title']} with context: {context_text[:300]} and score: {score}")
                else:
                    print(f"Recommendation skipped due to low score: {score} for {rec['title']}")
        except Exception as e:
            print(f"Error enriching recommendation {rec.get('title', 'Unknown')}: {e}")
            return None
    
    recommendations = await asyncio.gather(*[
        asyncio.to_thread(enrich_recommendation, rec) for rec in recommendations if rec
    ])

    set_session_status_field(
        session_id,
        rec_category,
        user_query,
        tag_id,
        field_key='is_processing',
        field_value=False
    )
    if message_converted_to_tag:
        # We need to also stop the processing of the session for this user message
        set_session_status_field(
            session_id,
            rec_category,
            original_query,
            None,
            field_key='is_processing',
            field_value=False
        )

    print(f"Enrichment and saving of recommendations completed for session {session_id} in category {rec_category} with user query: {user_query} and tag ID: {tag_id}")

async def get_recommendations_by_details(details, page=1):
    """
    Fetch recommendations based on the provided details.
    
    Args:
        details (dict): A dictionary containing the details to filter recommendations.
    
    Returns:
        list: A list of recommendations based on the provided details.
    """
    if not details:
        return []
    
    # print(f"Fetching recommendations by details: {details} on page {page}")
    
    processing_status = await asyncio.to_thread(get_session_status_field,
        details.get('session_id'),
        details.get('recommendation_category'),
        details.get('user_message'),
        details.get('selected_tag_id'),
        field_key='is_processing'
    )
    print(f"Processing status for session {details.get('session_id')}: {processing_status}")

    error_message = await asyncio.to_thread(get_session_status_field,
        details.get('session_id'),
        details.get('recommendation_category'),
        details.get('user_message'),
        details.get('selected_tag_id'),
        field_key='error_message'
    )

    possible_tag_switched_id = await asyncio.to_thread(get_session_status_field,
        details.get('session_id'),
        details.get('recommendation_category'),
        details.get('user_message'),
        details.get('selected_tag_id'),
        field_key='tag_switched_id'
    )

    if possible_tag_switched_id is not None:
        print(f"Possible tag switched ID for session {details.get('session_id')}: {possible_tag_switched_id}")
        details['tag_id'] = possible_tag_switched_id

    recommendations = await asyncio.to_thread(get_recommendations_using_details,details=details, page=page)
    # print(f"Recommendations fetched for session {details.get('session_id')}: {recommendations}")

    if recommendations and recommendations != {} and recommendations.get('start_next_set', False) == True:
        # If the flag to start next set is True then we need to generate more recommendations with same data
        asyncio.create_task(generate_alonis_qloo_powered_recommendations(
            details.get('session_id'),
            details.get('recommendation_category', 'Movies'),
            details.get('user_message'),
            is_tags_only=details.get('is_tags_only', False),
            selected_tag_id=details.get('tag_id')
        ))


    return recommendations, processing_status, error_message

