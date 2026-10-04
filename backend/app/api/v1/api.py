from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    traffic,
    vehicles,
    routes,
    optimization,
    zones,
    priority,
)

api_router = APIRouter()

# Health Check Endpoint
api_router.include_router(health.router, tags=["health"])

# Core Domain Module Endpoints
api_router.include_router(traffic.router, prefix="/traffic", tags=["traffic"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(optimization.router, prefix="/optimization", tags=["optimization"])
api_router.include_router(zones.router, prefix="/zones", tags=["zones"])
api_router.include_router(priority.router, prefix="/priority", tags=["priority"])
