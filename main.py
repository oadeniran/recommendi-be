from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import appENV, PORT
from routes import base_routes

## Define API prefix based on environment
prefix = "/" + ("recommendi" if appENV == "production"  else ("recommendi" if appENV == "development" else "dev"))

## Set API documentation details
title = f"Recommendi API for {appENV} Environment"
description = f"Recommendi API for {appENV} Documentation"

tags_metadata = [
    {
        "name": "Recommendi APIs",
        "description": "Endpoints to power recommendi",
    }
]

## Initialize FastAPI app
app = FastAPI(
    docs_url=prefix + "/docs",
    openapi_url=prefix + "/openapi.json",
    title=title,
    description=description,
    openapi_tags=tags_metadata,
)

## Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(base_routes.router, prefix=prefix)


if __name__ == "__main__":
    import uvicorn
    reload = True  if appENV != "production" else False
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=reload)