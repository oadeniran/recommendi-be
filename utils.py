from geopy.geocoders import GoogleV3
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import requests
from config import GOOGLE_API_KEY, COUNTRY_NAMES, SHAPEFILE_PATH
import json
import re
import unicodedata
from countryinfo import CountryInfo
from geopy.distance import geodesic
import geopandas as gpd
import pycountry
import os


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

def extract_country_from_text(text: str) -> str:
    """
    Extracts the country name from a text using regex and known country names.
    Returns the country name if found, else empty string.
    """
    text_lower = text.lower()
    
    # Check for full word match for each known country
    for country in COUNTRY_NAMES:
        pattern = r'\b' + re.escape(country) + r'\b'
        if re.search(pattern, text_lower):
            return country.title()  # Capitalize for display/use

    return text  # Return the original text if no country found

def get_capital_for_country(country_name: str) -> str:
    try:
        country = CountryInfo(country_name)
        return country.capital()
    except:
        return ""

def geocode_address(address: str) -> dict:
    """
    Geocode an address using Google Maps API.
    If `country_level` is True, will attempt to geocode only to the country level.
    """

    geolocator = GoogleV3(api_key=GOOGLE_API_KEY)
    print(f"Geocoding address: {address}")

    try:
        location = geolocator.geocode(address)

        if location:
            return {
                "latitude": location.latitude,
                "longitude": location.longitude
            }
        else:
            print(f"Could not geocode address: {address}")
            return {"latitude": 47.751076, "longitude": -120.740135}

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error: {str(e)}")
        return {"latitude": 47.751076, "longitude": -120.740135}
    
def get_max_radius_from_point(lat, lon, country_name):
    """
    Given a lat/lon and country name, compute the farthest distance (in km)
    from that point to any coordinate on the country's border.
    """
    try:
        if not os.path.exists(SHAPEFILE_PATH):
            raise FileNotFoundError(f"Shapefile not found at {SHAPEFILE_PATH}")

        world = gpd.read_file(SHAPEFILE_PATH)
        country = world[world['NAME'].str.lower() == country_name.lower()]
        if country.empty:
            # Try using ISO code
            country_code = pycountry.countries.get(name=country_name)
            if country_code:
                country = world[world['ISO_A3'] == country_code.alpha_3]
        if country.empty:
            return None

        geometry = country.iloc[0].geometry
        origin = (lat, lon)

        # Handle MultiPolygon and Polygon
        if geometry.type == 'MultiPolygon':
            max_distance = max(
                geodesic(origin, (coord[1], coord[0])).km
                for polygon in geometry.geoms
                for coord in polygon.exterior.coords
            )
        else:
            max_distance = max(
                geodesic(origin, (coord[1], coord[0])).km
                for coord in geometry.exterior.coords
            )

        return round(max_distance, 2)

    except Exception as e:
        print("Error:", e)
        return None


def get_all_location_details(address, country_level=False):
    """Returns full location details including geocode and max radius for country."""
    country, country_code, county, state, state_abbr, zip_code = get_address_details(address)

    if country_level:
        country_address = country or extract_country_from_text(address)
        capital = get_capital_for_country(country_address)
        address_to_geocode = f"{capital}, {country_address}" 
    else:
        address_to_geocode = address

    geocoded_address = geocode_address(address_to_geocode)
    lat = geocoded_address.get('latitude')
    lon = geocoded_address.get('longitude')

    max_radius = None
    if lat and lon and country:
        max_radius = get_max_radius_from_point(lat, lon, country)

    return {
        "county": county,
        "country": country,
        "country_code": country_code,
        "state": state,
        "state_abbr": state_abbr,
        "zip_code": zip_code,
        "latitude": lat,
        'longitude': lon,
        "max_radius": max_radius  # in kilometers
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

def clean_text(text):
    """
    Normalize a string by removing all punctuation, whitespace, emojis,
    and converting to lowercase.

    Args:
        text (str): The input string.

    Returns:
        str: The cleaned string.
    """
    if text is None:
        return None
    # Normalize Unicode (NFKD separates accents from letters)
    text = unicodedata.normalize('NFKD', text)

    # Remove all characters that are not alphanumeric (letters and digits)
    # This handles: punctuation, emojis, symbols, whitespace, etc.
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', text)

    return cleaned.lower()