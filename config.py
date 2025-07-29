from dotenv import load_dotenv
import os
import pycountry

# Load environment variables from .env file
load_dotenv()

appENV = os.getenv("APP_ENV", "local")  # Default to 'local' if not set
QLOO_API_URL = os.getenv("QLOO_API_URL", "https://api.qloo.com/v1/recommendations")
QLOO_API_KEY = os.getenv("QLOO_API_KEY", "")
DB_URL = os.getenv("DATABASE_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
PORT = int(os.getenv("PORT", 80))  # Default to 80 if not set
OAI_KEY = os.getenv("OAI_KEY", "")

RECOMMENDATIONS_PER_PAGE = 2
# Create a set of all country names (lowercase for matching)
COUNTRY_NAMES = {country.name.lower() for country in pycountry.countries}
SHAPEFILE_PATH = os.getenv("SHAPEFILE_PATH", "countries_data")  # Update with your shapefile path