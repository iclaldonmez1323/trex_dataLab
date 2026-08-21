"""trex DataLab - Main Application Entrypoint.

Refactored to Modular Monolith Architecture.
All core components are located under `app/`.
"""

from app.main import app  # Re-export FastAPI app instance

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
