from pymongo import MongoClient
from config import DB_URL, RECOMMENDATIONS_PER_PAGE
from utils import clean_text

db_client = MongoClient(DB_URL)
db_conn = db_client['recommendi_db']
recommendations_collection = db_conn['recommendations']
session_collection = db_conn['session_data']

def add_recommendation(recommendation):
    """
    Add a recommendation to the database.
    
    Args:
        recommendation (dict): The recommendation data to be added.
    
    Returns:
        str: The ID of the inserted recommendation.
    """
    result = recommendations_collection.insert_one(recommendation)
    return str(result.inserted_id)

def get_recommendations_using_details(details, page=None):
    """
    Get recommendations by the details to use.
    
    Args:
        details (dict): The details to use for filtering recommendations.
    
    Returns:
        list: A list of recommendations matching the details.
    """
    query = {
        'session_id': details.get('session_id'),
        "cleaned_user_message": clean_text(details.get('user_message')),
        "recommendation_category": details.get('recommendation_category'),
        'tag_id': details.get('tag_id'),
    }

    cursor = recommendations_collection.find(query)#.sort([("is_read_by_user", 1), ("date", -1), ("_id", -1)])  # Sort by date and then by _id in descending order

    if page is not None:
            skip = (page - 1) * RECOMMENDATIONS_PER_PAGE
            cursor = cursor.skip(skip)
            cursor = cursor.limit(RECOMMENDATIONS_PER_PAGE)

    recommendations = list(cursor)

    if page is not None and page == 1:
        if len(recommendations)  == 1:
            # We are using one recommendation with error in it to denote failuer to fetch so check if we have only one recommendation and it has error
            if recommendations[0].get('error'):
                return {
                    "recommendations": [],
                    "count": 0,
                    "page": page,
                    'has_next_page': False,
                    'start_next_set': False,
                    'total_recommendations': 0,
                    "status_code": 404,
                    'error' : recommendations[0].get('error', 'No recommendations found')
                }
        else:
            # Anything other than error means we have recommendations but we need tio check if its up to the page limit and if not then we still have to return empty recommendations
            if len(recommendations) < RECOMMENDATIONS_PER_PAGE:
                #print("Not enough for the page limit, returning empty recommendations.")
                return 
    
    # If the recommendations are found but not exactly amount for teh page then reurn None also
    if len(recommendations) < RECOMMENDATIONS_PER_PAGE and page is not None:
        return

    for rec in recommendations:
        rec['id'] = str(rec['_id'])
        del rec['_id']
        if 'date' in rec:
            rec['date'] = rec['date'].strftime("%Y-%m-%d %H:%M:%S")
    
    # # Shuffle the recommendations to provide a varied experience
    # random.shuffle(recommendations)
    
    total_recommendations = recommendations_collection.count_documents(query)

    return {
        "recommendations": [{k:v for k, v in recommendation.items() if k != 'tags_original'} for recommendation in recommendations],
        "count": len(recommendations),
        "page": page,
        'has_next_page': (page is not None and (RECOMMENDATIONS_PER_PAGE * int(page)) < total_recommendations),
        'start_next_set': (page is not None and ((total_recommendations - RECOMMENDATIONS_PER_PAGE * int(page)) < 3)),
        'total_recommendations': total_recommendations,
        "status_code": 200
    }

def get_session_data(session_id):
    """
    Get session data by session ID.
    
    Args:
        session_id (str): The session ID.
    
    Returns:
        dict: The session data.
    """
    session_data = session_collection.find_one({'session_id': session_id})
    if session_data:
        session_data['id'] = str(session_data['_id'])
        del session_data['_id']
    
    return session_data

def set_session_status_field(session_id, recommendation_category, user_message, selected_tag_id, field_key, field_value):
    """
    Set any field under a session's recommendation category.

    Args:
        session_id (str): The session ID.
        recommendation_category (str): The category of recommendations.
        user_message (str): The user's message (optional if selected_tag_id is provided).
        selected_tag_id (str): The selected tag ID.
        field_key (str): The specific field to set (e.g., 'is_processing').
        field_value (Any): The value to assign to the field.

    Returns:
        None
    """
    query = {'session_id': session_id}
    keys_l = []
    if user_message is not None:
        keys_l.append(clean_text(user_message))
    if selected_tag_id is not None:
        keys_l.append(selected_tag_id)
    
    key = ".".join(keys_l) if keys_l else None
    field_path = f"{recommendation_category}.{key}.{field_key}"

    update = {
        '$set': {
            field_path: field_value
        }
    }

    session_collection.update_one(query, update, upsert=True)

def get_session_status_field(session_id, recommendation_category, user_message, selected_tag_id, field_key):
    """
    Get the value of any field under a session's recommendation category.

    Args:
        session_id (str): The session ID.
        recommendation_category (str): The category of recommendations.
        user_message (str): The user's message (optional if selected_tag_id is provided).
        selected_tag_id (str): The selected tag ID.
        field_key (str): The specific field to retrieve (e.g., 'is_processing').

    Returns:
        Any or None: The field value if found, otherwise None.
    """
    query = {'session_id': session_id}
    keys_l = []
    if user_message is not None:
        keys_l.append(clean_text(user_message))
    if selected_tag_id is not None:
        keys_l.append(selected_tag_id)
    
    key = ".".join(keys_l) if keys_l else None
    field_path = f"{recommendation_category}.{key}.{field_key}"

    projection = {field_path: 1, '_id': 0}
    doc = session_collection.find_one(query, projection)

    if not doc:
        return None

    # Traverse the nested path to retrieve the value
    parts = field_path.split('.')
    for part in parts:
        if isinstance(doc, dict) and part in doc:
            doc = doc[part]
        else:
            return None
    return doc