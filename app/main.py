import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import (
    views,
    dataset,
    quality,
    preprocessing,
    visualization,
    ml,
    ai_assistant,
    export
)


def create_app() -> FastAPI:
    """FastAPI Application Factory for trex DataLab."""
    app = FastAPI(title="trex DataLab API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all routers
    app.include_router(views.router)
    app.include_router(dataset.router)
    app.include_router(quality.router)
    app.include_router(preprocessing.router)
    app.include_router(visualization.router)
    app.include_router(ml.router)
    app.include_router(ai_assistant.router)
    app.include_router(export.router)

    # Static file mounts
    if os.path.exists("static/portfolio/grafikler"):
        app.mount("/portfolio/grafikler", StaticFiles(directory="static/portfolio/grafikler"), name="portfolio_grafikler")
    elif os.path.exists("portfolio/grafikler"):
        app.mount("/portfolio/grafikler", StaticFiles(directory="portfolio/grafikler"), name="portfolio_grafikler")

    if os.path.exists("static/components"):
        app.mount("/components", StaticFiles(directory="static/components"), name="components")
    elif os.path.exists("components"):
        app.mount("/components", StaticFiles(directory="components"), name="components")

    if os.path.exists("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")

    return app


app = create_app()
