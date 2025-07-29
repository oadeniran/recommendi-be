from config import QLOO_API_URL, QLOO_API_KEY
import requests
import re
from bs4 import BeautifulSoup

ENTITIES= {
    "movies": "urn:entity:movie",
    "tv_shows": "urn:entity:tv_show",
    'books': "urn:entity:book",
    'destinations': "urn:entity:destination",
    'places': "urn:entity:place",
}

QLOO_HEADER = {
    'X-Api-Key': QLOO_API_KEY,
    'accept': 'application/json'
}

def get_all_possible_recommendation_categories():
    """
    Get all possible recommendation categories.
    
    Returns:
        list: A list of all possible recommendation categories.
    """
    return list(ENTITIES.keys())

def is_country_level(category):
    """
    Check if the category is country level.
    
    Args:
        category (str): The category to check.
    
    Returns:
        bool: True if the category is country level, False otherwise.
    """
    return category.lower() in ['movies', 'books']

def get_qloo_rec_endpoint(entity, tags, page, state= None, country_code=None, longitude=None, latitude=None, should_be_recent=False, radius=None):
    # Year based limit
    year_limit = ""
    if entity in ["urn:entity:movie", "urn:entity:tv_show"]:
        year_limit = "&filter.release_year.min=2020"  if should_be_recent else "&filter.release_year.min=2000"
    elif entity == "urn:entity:book":
        year_limit = "&filter.publication_year.min=2020" if should_be_recent else "&filter.publication_year.min=2000"

    location_str = ''
    if state is not None and country_code is not None:
        location_str = f"&filter.geocode.country_code={country_code}&filter.geocode.filter.geocode.admin1_region={state}"
    elif longitude is not None and latitude is not None:
        radius_str = ""
        if radius is not None:
            try:
                radius = int(radius)
                radius_str = str(radius)
            except ValueError:
                print(f"Invalid radius value: {radius}. Using default radius of 900 km.")
                radius_str = "900"
        else:
            radius_str = "900"  # Default radius of 900 km
            
        location_str = f"&signal.location=POINT%28{longitude}%20{latitude}%29&signal.location.radius={radius_str}"

    return f"{QLOO_API_URL}v2/insights?filter.type={entity}&filter.tags={tags}{location_str}&page={page}{year_limit}"

def get_qloo_search_endpoint(entity, query, location=None ,page=1):
    location_str = ''
    if location is not None:
        location_str = f"&filter.location={location.get('latitude')},{location.get('longitude')}"
    return f"{QLOO_API_URL}/search?query={query}&types={entity}{location_str}&page={page}&sort_by=popularity"

def get_qloo_tags_endpoint(entity, query= None):
    if query is not None and query != "":
        query = f"&filter.query={query}"
    return f"{QLOO_API_URL}v2/tags?feature.typo_tolerance=true&filter.parents.types={entity}{query}"

def make_qloo_request(endpoint):
    response = requests.get(endpoint, headers=QLOO_HEADER)
    if response.status_code != 200:
        raise Exception(f"Error fetching data from Qloo API: {response.status_code} - {response.text}")
    return response.json()

def get_qloo_tag_to_use_for_non_specific(entity_name, query = None, backups= None):
    qloo_enity = ENTITIES.get(entity_name)
    if not qloo_enity:
        raise ValueError(f"Invalid entity name: {entity_name}")
    look_for_genre = entity_name in ['movies', 'tv_shows', 'books']
    endpoint = get_qloo_tags_endpoint(qloo_enity, query)
    data = make_qloo_request(endpoint)
    for tag in data.get("results", {}).get("tags", []):
        tag_name = tag.get("name", "").strip().lower()
        tag_id = tag.get("id") or tag.get("tag_id")
        if not tag_name or not tag_id:
            continue

        if look_for_genre:
            tag_type_parts = tag.get('type', '').lower().split(':')
            # Check if 'genre' is an exact part of the type, not a substring
            if 'genre' in tag_type_parts:
                return tag_id
        else:
            # Return the first valid tag
            return tag_id
    return None


def clean_html_text(html_text):
    # Define tags whose entire content should be removed
    remove_content_tags = ['i', 'em', 'script', 'style']

    soup = BeautifulSoup(html_text, "html.parser")

    # Remove specified tags and their content
    for tag in soup.find_all(remove_content_tags):
        tag.decompose()

    # Get remaining text
    cleaned_text = soup.get_text(separator=' ', strip=True)

    return cleaned_text

def transform_movie_entity(entity):
    """
    Transforms a single entity with improved tag filtering and 'where_to_watch' extraction.
    """
    # --- 1. Process all tag logic in a single, efficient loop ---
    filtered_tags = []
    where_to_watch_list = []
    original_tags = entity.get('tags', [])

    first_genre = None
    for tag in original_tags:
        tag_name = tag.get('name')
        tag_type = tag.get('type')
        tag_id = tag.get('id') or tag.get('tag_id')


        # Skip any tag that is missing essential info
        if not tag_name or not tag_type or not tag_id:
            continue

        # Rule 1: Extract streaming services for 'extra_data'
        if 'streaming_service' in tag_type:
            where_to_watch_list.append(tag_name)

        # Rule 2: Add all genres to the final 'tags' list
        elif 'genre' in tag_type:
            filtered_tags.append({"name" : tag_name, "id": tag_id})
            if not first_genre:
                first_genre = tag_name

        # Rule 3: Add single-word keywords to the final 'tags' list
        elif 'keyword' in tag_type and ' ' not in tag_name.strip():
            filtered_tags.append({"name" : tag_name, "id": tag_id})

    # --- 2. Create and populate the 'extra_data' dictionary ---
    extra_data = {
        'duration': entity.get('properties', {}).get('duration'),
        'content_rating': entity.get('properties', {}).get('content_rating'),
        'popularity': entity.get('popularity'),
    }

    # Process external source data
    source_external = entity.get('external', {})
    if source_external:
        for key, value_list in source_external.items():
            if isinstance(value_list, list) and value_list and isinstance(value_list[0], dict):
                first_item = value_list[0]
                extra_data[key] = {k: v for k, v in first_item.items() if k != 'id'}
    extra_data['where_to_watch'] = where_to_watch_list

    try:
    # --- 3. Assemble and return the final dictionary ---
        return {
            'title': entity.get('name'),
            'id': entity.get('id') or entity.get('entity_id'),
            'release_date': entity.get('properties', {}).get('release_date'),
            'description': clean_html_text(entity.get('properties', {}).get('description')),
            'genre': first_genre,
            'image': entity.get('properties', {}).get('image'),
            # Clean the final extra_data to remove empty values (e.g., if where_to_watch is empty)
            'extra_data': {k: v for k, v in extra_data.items() if v},
            'tags': filtered_tags,
            'tags_original': original_tags,
        }
    except Exception as e:
        print(f"Error transforming movie entity: {e}")
        return 

def _get_corrected_tag_id(tag_id, tag_type):
    """
    Correctly inserts 'place' into a tag ID if it's missing.
    e.g., urn:tag:genre:restaurant -> urn:tag:genre:place:restaurant
    """
    if not tag_id or not tag_type:
        return tag_id

    id_parts = tag_id.split(':')
    type_parts = tag_type.split(':')
    
    # Position where 'place' should be
    insert_pos = len(type_parts)
    
    # Check if 'place' is already in the correct position
    if len(id_parts) > insert_pos and id_parts[insert_pos] == 'place':
        return tag_id # It's already correct, do nothing

    # If not, insert 'place' and rebuild the ID
    id_parts.insert(insert_pos, 'place')
    return ':'.join(id_parts)


def transform_place_entity(entity):
    """
    Transforms a single place entity dictionary, including hours and specialty dishes.
    """
    # Get the nested properties dictionary once for cleaner access
    properties = entity.get('properties', {})

    # --- 1. Process all tags ---
    filtered_tags = []
    seen_names = set()  # To avoid duplicates
    
    # Process main tags (genres, categories, amenities) from the top-level 'tags' key
    original_tags = entity.get('tags', [])
    all_tags_to_process = original_tags + \
                          properties.get('specialty_dishes', []) + \
                          properties.get('good_for', [])
    for tag in all_tags_to_process:
        tag_name = tag.get('name')
        tag_type = tag.get('type')
        tag_id = tag.get('id') or tag.get('tag_id')
        if tag_id is not None:
            corrected_id = _get_corrected_tag_id(tag_id, tag_type)
            tag_id = corrected_id


        if not tag_name or not tag_type or not tag_id:
            continue

        #if 'genre' in tag_type or 'category' in tag_type or 'amenity' in tag_type:
        if tag_name not in seen_names:
            seen_names.add(tag_name)
            filtered_tags.append({"name": tag_name, "id": tag_id})

    # --- 2. Create and populate the 'extra_data' dictionary ---
    extra_data = {
        'website': properties.get('website'),
        'phone': properties.get('phone'),
        'business_rating': properties.get('business_rating'),
        'is_closed': properties.get('is_closed'),
        'hotel_class': properties.get('hotel_class'),
        'number_of_rooms': properties.get('number_of_rooms'),
        'price_range': properties.get('price_range'),
        'price_level': properties.get('price_level'),
        'keywords': properties.get('keywords'),
        'location': entity.get('location'),
        'popularity': entity.get('popularity')
    }

    # Process and clean 'hours' data if it exists in properties
    source_hours = properties.get('hours')
    if source_hours:
        cleaned_hours = {}
        for day, time_list in source_hours.items():
            cleaned_times = []
            for time_entry in time_list:
                cleaned_entry = {}
                opens = time_entry.get('opens')
                closes = time_entry.get('closes')
                if opens:
                    cleaned_entry['opens'] = opens.replace('T', '')
                if closes:
                    cleaned_entry['closes'] = closes.replace('T', '')
                if cleaned_entry:
                    cleaned_times.append(cleaned_entry)
            if cleaned_times:
                cleaned_hours[day] = cleaned_times
        if cleaned_hours:
            extra_data['hours'] = cleaned_hours

    # Process external data (checking both top-level and properties)
    source_external = entity.get('external', {}) or properties.get('external', {})
    if source_external:
        for key, value_list in source_external.items():
            if isinstance(value_list, list) and value_list and isinstance(value_list[0], dict):
                first_item = value_list[0]
                extra_data[key] = {k: v for k, v in first_item.items() if k != 'id'}

    # --- 3. Safely extract the primary image ---
    # Handle cases where image is a list ('images') or a single object ('image')
    image_prop = properties.get('images') or properties.get('image')
    image_obj = {}
    if isinstance(image_prop, list) and image_prop:
        image_obj = image_prop[0]
    elif isinstance(image_prop, dict):
        image_obj = image_prop

    # --- 4. Assemble and return the final dictionary ---
    return {
        'title': entity.get('name'),
        'id': entity.get('id') or entity.get('entity_id'),
        'description': clean_html_text(properties.get('description', "")),
        'address': properties.get('address'),
        'image': image_obj,
        'tags': filtered_tags,
        'tags_original': original_tags,
        'extra_data': {k: v for k, v in extra_data.items() if v is not None and v != ''}
    }

def transform_book_entity(entity):
    """
    Transforms a single book entity, including filtered tags.
    """

    # helper to clean author
    def clean_author(author_str: str) -> str:
        match = re.match(r"^\d{4},\s*(.*)", author_str)
        return match.group(1) if match else author_str
    
    # Get the nested properties dictionary once
    properties = entity.get('properties', {})

    # --- 1. Process tags for genres and keywords ---
    filtered_tags = []
    original_tags = entity.get('tags', [])

    for tag in original_tags:
        tag_name = tag.get('name')
        tag_type = tag.get('type')
        tag_id = tag.get('id') or tag.get('tag_id')

        # Skip any tag that is missing essential info
        if not tag_name or not tag_type or not tag_id:
            continue

        # Add tag if its type is 'genre' OR 'keyword'
        if 'genre' in tag_type or 'keyword' in tag_type:
            filtered_tags.append({"name" : tag_name, "id": tag_id})

    # --- 2. Create and populate the 'extra_data' dictionary ---
    extra_data = {
        'publisher': properties.get('publisher'),
        'page_count': properties.get('page_count'),
        'popularity': entity.get('popularity')
    }

    # Process external data from other sources
    source_external = entity.get('external', {})
    if source_external:
        for key, value_list in source_external.items():
            if isinstance(value_list, list) and value_list and isinstance(value_list[0], dict):
                first_item = value_list[0]
                extra_data[key] = {k: v for k, v in first_item.items() if k != 'id'}

    # --- 3. Assemble and return the final dictionary ---
    return {
        'title': entity.get('name'),
        'id': entity.get('id') or entity.get('entity_id'),
        'author': clean_author(entity.get('disambiguation')) if entity.get('disambiguation') else None,
        'publication_date': properties.get('publication_date'),
        'image': properties.get('image'),
        'description': clean_html_text(properties.get('description')),
        'extra_data': {k: v for k, v in extra_data.items() if v},
        'tags': filtered_tags,
        'tags_original': original_tags,
    }


def get_qloo_search_recommendations(entity_name, recommendation_fetch_data, page=1):
    qloo_entity = ENTITIES.get(entity_name)
    if not qloo_entity:
        raise ValueError(f"Invalid entity name: {entity_name}")
    
    location_data = None
    if entity_name in ['places', 'destinations']:
        location_data = recommendation_fetch_data.get('location_details', {})

    
    keyword = recommendation_fetch_data.get('keyword', '') 
    generic_term = recommendation_fetch_data.get('generic_term', '')

    query = keyword if len(keyword) > 0 else generic_term 
    
    endpoint = get_qloo_search_endpoint(qloo_entity, query, location_data, page)
    print(f"Fetching search recommendations from Qloo API for {entity_name} with query '{query}' on page {page} with endpoint {endpoint}")
    
    data = make_qloo_request(endpoint)

    
    recommendation_entities = []
    if entity_name in ["movies", "tv_shows"]:
        recommendation_entities += [
            transform_movie_entity(entity)
            for entity in data.get("results", [])
        ]
    elif entity_name == "books":
        recommendation_entities += [
            transform_book_entity(entity)
            for entity in data.get("results", [])
        ]
    elif entity_name in ["destinations", "places"]:
        recommendation_entities += [
            transform_place_entity(entity)
            for entity in data.get("results", [])
        ]
    print(f"Found {len(recommendation_entities)} recommendations for {entity_name} with query '{query}' on page {page}")
    if recommendation_entities == []:
        print(f"No recommendations found for {entity_name} with query '{query}' on page {page}")
        print("Switching to backup keywords")
        all_backup_keywords = recommendation_fetch_data.get('backup_keywords',"").strip().split(',')
        if not all_backup_keywords:
            print("No backup keywords found, returning empty list")
            return recommendation_entities
        backups_checked = 0
        while recommendation_entities == [] and backups_checked < len(all_backup_keywords):
            backup_keyword = all_backup_keywords[backups_checked].strip()
            print(f"Trying backup keyword: {backup_keyword}")
            endpoint = get_qloo_search_endpoint(qloo_entity, backup_keyword, location_data, page)
            print(f"Fetching search recommendations from Qloo API for {entity_name} with query '{backup_keyword}' on page {page} with endpoint {endpoint}")
            data = make_qloo_request(endpoint)
            if entity_name in ["movies", "tv_shows"]:
                recommendation_entities += [
                    transform_movie_entity(entity)
                    for entity in data.get("results", [])
                ]
            elif entity_name == "books":
                recommendation_entities += [
                    transform_book_entity(entity)
                    for entity in data.get("results", [])
                ]
            elif entity_name in ["destinations", "places"]:
                recommendation_entities += [
                    transform_place_entity(entity)
                    for entity in data.get("results", [])
                ]
            backups_checked += 1
    print(f"Found {len(recommendation_entities)} recommendations for {entity_name} on page {page}")
    return recommendation_entities

def get_qloo_recommendations_by_tag_id(entity_name, tag_id, page, location=None, should_be_recent=False):
    qloo_entity = ENTITIES.get(entity_name)
    if not qloo_entity:
        raise ValueError(f"Invalid entity name: {entity_name}")
    
    # Remove the location data not needed based on entity type
    if entity_name in ['places', 'destinations']:
        if location is not None:
            del location['latitude']
            del location['longitude']
    elif entity_name in ['movies', 'tv_shows', 'books']:
        if location is not None:
            del location['state']
            del location['country_code']
    
    endpoint = get_qloo_rec_endpoint(qloo_entity, tag_id, page, 
                                     location.get('state') if location else None, 
                                     location.get('country_code') if location else None, 
                                     longitude=location.get('longitude') if location else None, 
                                     latitude=location.get('latitude') if location else None,
                                     should_be_recent=should_be_recent,
                                     radius = location.get('max_radius') if location else None)
    print(f"Fetching recommendations from Qloo API for {entity_name} with tag ID {tag_id} with endpoint {endpoint}")
    
    data = make_qloo_request(endpoint)
    
    recommendation_entities = []
    if entity_name in ["movies", "tv_shows"]:
        recommendation_entities += [
            transform_movie_entity(entity)
            for entity in data.get("results", {}).get("entities", [])
        ]
    elif entity_name == "books":
        recommendation_entities += [
            transform_book_entity(entity)
            for entity in data.get("results", {}).get("entities", [])
        ]
    elif entity_name in ["destinations", "places"]:
        recommendation_entities += [
            transform_place_entity(entity)
            for entity in data.get("results", {}).get("entities", [])
        ]
    
    print(f"Found {len(recommendation_entities)} recommendations for {entity_name} with tag ID {tag_id} on page {page}")
    return recommendation_entities
