from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import setup_logging, setup_openai_client
from routers import health, instrument


def create_app():
    """Create and configure FastAPI application."""
    logger = setup_logging()
    client = setup_openai_client()

    app = FastAPI(
        title="DD Instrumenter Agent",
        description="A FastAPI server for the DD Instrumenter Agent",
        version="1.0.0"
    )

    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

    # Store dependencies in app state
    app.state.openai_client = client
    app.state.logger = logger

    # Include routers
    app.include_router(health.router)
    app.include_router(instrument.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
