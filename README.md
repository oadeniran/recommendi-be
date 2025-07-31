# Recommendi Backend API

A FastAPI-based recommendation system that provides intelligent recommendations for movies, TV shows, books, and places using advanced LLM processing and the Qloo API.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Request Flow](#request-flow)
- [Core Components](#core-components)
- [API Endpoints](#api-endpoints)
- [Installation and Setup](#installation-and-setup)
- [Environment Variables](#environment-variables)

## Architecture Overview

The Recommendi backend follows a clean, layered architecture that separates concerns across different modules:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │ -> │     Routes      │ -> │  Routes Logic   │
│    (main.py)    │    │ (base_routes.py)│    │     Layer       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                              ┌─────────────────┐
                                              │   Core Layer    │
                                              │  (Business      │
                                              │     Logic)      │
                                              └─────────────────┘
                                                       │
                               ┌─────────────────────────────────────┐
                               │                                     │
                         ┌─────▼─────┐  ┌─────────────┐  ┌─────────▼─────┐
                         │ LLM Core  │  │  Qloo Core  │  │ Database (DB) │
                         │(AI Logic) │  │ (External   │  │   & Utils     │
                         │           │  │   API)      │  │               │
                         └───────────┘  └─────────────┘  └───────────────┘
```

## Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration and environment variables
├── db.py                  # Database operations (MongoDB)
├── utils.py               # Utility functions (geocoding, text processing)
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
│
├── routes/
│   └── base_routes.py     # API endpoint definitions
│
├── routesLogic/
│   └── recommendationRoutesLogic.py  # Business logic for routes
│
├── dtos/
│   └── recommendation_fetch_dto.py   # Data Transfer Objects
│
└── core/
    ├── llm_core.py        # LLM integration and processing
    ├── qloo_core.py       # Qloo API integration
    ├── recommednations.py # Core recommendation engine
    ├── prompts.py         # LLM prompt templates
    └── background_tasks.py # Async background processing
```

## Request Flow

### 1. API Request Flow
Here's how a typical recommendation request flows through the system:

```
1. Client Request
   │
   ▼
2. FastAPI Router (base_routes.py)
   │ - Validates request data
   │ - Maps categories to internal format
   │
   ▼
3. Routes Logic Layer (recommendationRoutesLogic.py)
   │ - Orchestrates the recommendation process
   │ - Handles retries and error scenarios
   │
   ▼
4. Core Recommendation Engine (recommednations.py)
   │ - Main business logic
   │ - Coordinates between LLM and Qloo APIs
   │
   ├─▼─ LLM Processing (llm_core.py)
   │    │ - Analyzes user message
   │    │ - Extracts keywords and intent
   │    │ - Scores recommendations
   │    │
   └─▼─ Qloo API Integration (qloo_core.py)
        │ - Fetches recommendations
        │ - Transforms API responses
        │
        ▼
5. Database Operations (db.py)
   │ - Stores processed recommendations
   │ - Manages session state
   │
   ▼
6. Response to Client
```

### 2. Detailed Processing Pipeline

#### Phase 1: Message Analysis
1. **User Input**: Raw user message (e.g., "I want movies like The Matrix")
2. **LLM Processing**: 
   - Uses `MESSAGE_DECOMPOSITION_PROMPT` to analyze the message
   - Extracts structured data:
     ```json
     {
       "is_valid": true,
       "is_specific": true,
       "keyword": "sci-fi action",
       "generic_term": "",
       "location": "",
       "should_be_recent": false,
       "backup_keywords": "sci-fi,action,futuristic"
     }
     ```

#### Phase 2: Recommendation Fetching
1. **Route Decision**: Based on `is_specific` flag:
   - **Specific requests**: Use Qloo Search API
   - **Generic requests**: Convert to tags using Qloo Tags API

2. **External API Calls**:
   - **Search-based**: `get_qloo_search_recommendations()`
   - **Tag-based**: `get_qloo_recommendations_by_tag_id()`

#### Phase 3: Data Enhancement
1. **Response Transformation**: Raw Qloo data → Structured format
2. **LLM Context Generation**: Each recommendation gets contextual explanation
3. **Quality Filtering**: Recommendations scored 1-10, only 6+ saved
4. **Database Storage**: Enriched recommendations stored with session data

## Core Components

### 1. Routes Layer (`routes/base_routes.py`)
**Purpose**: API endpoint definitions and request validation

**Key Endpoints**:
- `GET /available-entities`: Returns supported recommendation categories
- `POST /recommendations`: Main recommendation generation endpoint
- `GET /recommendations/{session_id}/details`: Retrieve stored recommendations

**Category Mapping**:
```python
ENTITIES_FORMATTED = {
    "Movies": "movies",
    "TV Shows": "tv_shows",
    "Books": "books",
    "Places": "places"
}
```

### 2. Routes Logic Layer (`routesLogic/recommendationRoutesLogic.py`)
**Purpose**: Orchestrates the recommendation process with retry logic

**Key Functions**:
- `generate_recommendations()`: Main entry point for new recommendations
- `get_recommendations_by_details()`: Retrieves existing recommendations with retry logic

**Features**:
- Automatic background task triggering
- Retry mechanism (up to 3 attempts)
- Processing status management

### 3. Core Recommendation Engine (`core/recommednations.py`)
**Purpose**: Main business logic for recommendation generation

**Key Functions**:
- `generate_alonis_qloo_powered_recommendations()`: Main async recommendation generator
- `enrich_and_save_recommendations()`: Enhances recommendations with AI context
- `get_recommendations_by_details()`: Fetches stored recommendations

**Processing Flow**:
1. **Session Management**: Tracks processing status to prevent duplicates
2. **Message Analysis**: Uses LLM to decompose user intent
3. **Location Processing**: Geocoding and radius calculation for place-based queries
4. **Recommendation Fetching**: Calls appropriate Qloo API endpoints
5. **Quality Enhancement**: AI-powered context generation and scoring
6. **Data Persistence**: Stores results in MongoDB

### 4. LLM Core (`core/llm_core.py`)
**Purpose**: AI/LLM integration for intelligent text processing

**Key Functions**:
- `get_recommendation_data_from_user_message()`: Analyzes user intent
- `get_context_and_score_for_recommndation_text()`: Generates explanation context

**AI Processing**:
- Uses OpenAI GPT-4o-mini model
- Structured prompt engineering for consistent outputs
- JSON extraction from LLM responses

### 5. Qloo Core (`core/qloo_core.py`)
**Purpose**: External API integration with Qloo recommendation service

**Key Functions**:
- `get_qloo_search_recommendations()`: Search-based recommendations
- `get_qloo_recommendations_by_tag_id()`: Tag-based recommendations
- `get_qloo_tag_to_use_for_non_specific()`: Converts generic terms to tags

**Data Transformation**:
- **Movies/TV Shows**: `transform_movie_entity()`
- **Books**: `transform_book_entity()`
- **Places**: `transform_place_entity()`

**Features**:
- Automatic retry with backup keywords
- Location-aware filtering
- Content filtering (recent/popular)

### 6. Database Layer (`db.py`)
**Purpose**: MongoDB operations for data persistence

**Collections**:
- `recommendations`: Stores processed recommendations
- `session_data`: Manages user session state and processing flags

**Key Functions**:
- `add_recommendation()`: Stores new recommendations
- `get_recommendations_using_details()`: Retrieves with pagination
- `set_session_status_field()` / `get_session_status_field()`: Session management

## API Endpoints

### 1. Get Available Categories
```http
GET /available-entities
```
Returns list of supported recommendation categories with UI metadata.

### 2. Generate Recommendations
```http
POST /recommendations
Content-Type: application/json

{
    "session_id": "user-session-123",
    "selected_category": "Movies",
    "user_message": "I want action movies like John Wick",
    "is_tags_only": false,
    "selected_tag_id": null
}
```

### 3. Get Recommendation Details
```http
GET /recommendations/{session_id}/details?recommendation_category=Movies&user_message=action movies&page=1
```

## Installation and Setup

### Prerequisites
- Python 3.8+
- MongoDB database
- OpenAI API key
- Qloo API key
- Google Maps API key (for geocoding)

### Installation Steps

1. **Clone and Setup**:
```bash
cd backend
pip install -r requirements.txt
```

2. **Environment Configuration**:
Create a `.env` file in the backend directory:
```env
APP_ENV=development
DATABASE_URL=mongodb://localhost:27017
OAI_KEY=your_openai_api_key
QLOO_API_KEY=your_qloo_api_key
QLOO_API_URL=https://api.qloo.com/
GOOGLE_API_KEY=your_google_maps_api_key
PORT=8000
SHAPEFILE_PATH=countries_data
```

3. **Run the Application**:
```bash
# Development
python main.py

# Production
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker Deployment
```bash
docker build -t recommendi-backend .
docker run -p 8000:8000 --env-file .env recommendi-backend
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `APP_ENV` | Environment (local/development/production) | Yes |
| `DATABASE_URL` | MongoDB connection string | Yes |
| `OAI_KEY` | OpenAI API key for LLM processing | Yes |
| `QLOO_API_KEY` | Qloo API key for recommendations | Yes |
| `QLOO_API_URL` | Qloo API base URL | Yes |
| `GOOGLE_API_KEY` | Google Maps API for geocoding | Yes |
| `PORT` | Server port (default: 80) | No |
| `SHAPEFILE_PATH` | Path to country boundary data | No |

## Key Features

### 1. Intelligent Message Processing
- Natural language understanding using LLM
- Automatic keyword extraction and intent recognition
- Support for location-based queries
- Fallback mechanisms for ambiguous requests

### 2. Multi-Source Recommendations
- Qloo API integration for high-quality recommendations
- Search-based and tag-based recommendation strategies
- Automatic backup keyword usage when primary search fails

### 3. AI-Enhanced Context
- Each recommendation includes AI-generated explanation
- Quality scoring (1-10) with automatic filtering
- Personalized context based on user's original request

### 4. Session Management
- Persistent session tracking across requests
- Processing status management to prevent duplicates
- Pagination support for large result sets

### 5. Location Intelligence
- Automatic geocoding for place-based queries
- Country/region boundary awareness
- Distance-based filtering with automatic radius calculation

This architecture ensures scalable, intelligent, and user-friendly recommendation generation while maintaining clean separation of concerns and robust error handling.
