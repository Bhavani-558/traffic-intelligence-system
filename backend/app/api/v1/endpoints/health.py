from fastapi import APIRouter
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns the operational status of the Traffic Optimization backend service.",
)
def get_health() -> HealthResponse:
    """Return health check status."""
    return HealthResponse(
        status="ok",
        service=settings.SERVICE_NAME,
    )
