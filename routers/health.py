from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse, FileResponse

router = APIRouter()


@router.get("/")
async def index():
    """
    Serve the frontend HTML page.
    """
    return FileResponse("frontend/index.html")


@router.get("/health")
async def health_check():
    """
    Health check endpoint that returns the server status.
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        status_code=200
    )
