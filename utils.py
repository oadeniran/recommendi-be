from geopy.geocoders import GoogleV3
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import requests
from config import GOOGLE_API_KEY
import json
import re


def dict_to_string(d, explanations=None, indent=0, normalize_text=False):
    def normalize(s):
        return s.replace('_', ' ').title() if normalize_text else s

    result = []
    prefix = " " * indent

    if explanations and len(explanations) > 0:
        for key, value in d.items():
            key_display = normalize(key)
            if isinstance(value, dict):
                value_str = ', '.join(f'{normalize(k)}: {v}' for k, v in value.items())
                result.append(f'{prefix}{key_display}: {explanations.get(key, "")}: value(numeric) can be {value_str}')
            elif isinstance(value, range):
                value_str = f'{value.start} to {value.stop - 1}'
                result.append(f'{prefix}{key_display}: {explanations.get(key, "")}: score user with a numeric value between {value_str}')
            else:
                result.append(f'{prefix}{key_display}: {value}')
    else:
        for key, value in d.items():
            key_display = normalize(key)
            if isinstance(value, dict):
                result.append(f'{prefix}{key_display}:')
                result.append(dict_to_string(value, explanations=None, indent=indent + 2, normalize_text=normalize_text))
            elif isinstance(value, list):
                result.append(f'{prefix}{key_display}:')
                for item in value:
                    if isinstance(item, dict):
                        result.append(dict_to_string(item, explanations=None, indent=indent + 2, normalize_text=normalize_text))
                    else:
                        item_display = normalize(item) if isinstance(item, str) else item
                        result.append(f'{" " * (indent + 2)}- {item_display}')
            elif isinstance(value, range):
                value_str = f'{value.start} to {value.stop - 1}'
                result.append(f'{prefix}{key_display}: {value_str}')
            else:
                value_display = normalize(value) if isinstance(value, str) else value
                result.append(f'{prefix}{key_display}: {value_display}')
                
    return '\n'.join(result)

def get_address_details(address):
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": GOOGLE_API_KEY}

        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] != "OK":
            return None, None, None, None, None, None

        country, country_code, county, state, state_abbr, zip_code = None, None, None, None, None, None

        for result in data["results"]:
            for component in result["address_components"]:
                print(component)
                if "administrative_area_level_2" in component["types"]:  # County
                    county = component["long_name"].replace(" County", "")
                if "administrative_area_level_1" in component["types"]:  # State
                    state = component["long_name"]
                    state_abbr = component["short_name"]
                if "postal_code" in component["types"]:  # ZIP Code
                    zip_code = component["long_name"]
                if "country" in component["types"]:  # Country
                    country = component["long_name"]
                    country_code = component["short_name"]

        return country, country_code, county, state, state_abbr, zip_code

def geocode_address(address: str) -> dict:
    """
    This function receives a string of text which is an address and
    uses Google Maps API to identify the latitude and longitude of that address. Keep my API key safe and protected.
    If you wanna know more, read about geocoding here: https://developers.google.com/maps/documentation/javascript/geocoding
    Read about how geopy uses google Geocoder here https://snyk.io/advisor/python/geopy/functions/geopy.geocoders.GoogleV3
    """
    geolocator = GoogleV3(api_key=GOOGLE_API_KEY)
    try:
        location = geolocator.geocode(address)
        if location:
            return {"latitude": location.latitude, "longitude": location.longitude}
            # return location.latitude, location.longitude
        else:
            print(f"Could not geocode address: {address}")
            return {
                "latitude": 47.751076, # Default to Washington State coordinates
                "longitude": -120.740135
            }
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error: {str(e)}")
        return {
                "latitude": 47.751076, # Default to Washington State coordinates
                "longitude": -120.740135
            }
    
def get_all_location_details(address):
    """ This function receives a string of text which is an address and returns a dictionary with the following keys:
    - county: The county of the address
    - country: The country of the address
    - country_code: The country code of the address
    - state: The state of the address
    - state_abbr: The state abbreviation of the address
    - zip_code: The zip code of the address
    It also returns the latitude and longitude of the address.
    """
    country, country_code, county, state, state_abbr, zip_code = get_address_details(address)
    geocoded_address = geocode_address(address)
    return {
        "county": county,
        "country": country,
        "country_code": country_code,
        "state": state,
        "state_abbr": state_abbr,
        "zip_code": zip_code,
        "latitude": geocoded_address.get('latitude'),
        'longitude': geocoded_address.get('longitude')
    }


def extract_dictionary_from_string(input_string):
    # Regular expression to find dictionary-like structure in the string
    dict_pattern = re.compile(r'\{.*?\}', re.DOTALL)
    
    # Search for the dictionary-like structure
    match = dict_pattern.search(input_string)
    
    if match:
        dict_string = match.group(0)
        
        # Attempt parsing the string to JSON
        dictionary = clean_and_parse_json(dict_string)
        return dictionary
    else:
        print("Error: No dictionary-like structure found in the input string.")
        return None

def clean_and_parse_json(input_string):
    # Step 1: Clean input by removing newline characters and excessive whitespace
    cleaned_string = re.sub(r'[\n\t]', '', input_string).strip()
    
    # Step 2: Convert single quotes to double quotes if needed
    #cleaned_string = cleaned_string.replace("'", '"')
    
    # Step 3: Handle any trailing commas inside the dictionary
    cleaned_string = re.sub(r',(\s*[\}\]])', r'\1', cleaned_string)
    
    # Step 4: Try to parse the cleaned string into a JSON object
    try:
        dictionary = json.loads(cleaned_string)
        return dictionary
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None