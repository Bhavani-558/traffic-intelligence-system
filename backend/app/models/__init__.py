"""Domain data models for vehicles and traffic metrics."""
from app.models.vehicle import (
    VehicleBase,
    VehicleCreate,
    Vehicle,
    VehicleListResponse,
)
from app.models.traffic import (
    RoadSegmentTraffic,
    CongestedSegment,
    TrafficInformationResponse,
)
from app.models.route import (
    Coordinates,
    RouteRequest,
    RouteResponse,
)

__all__ = [
    "VehicleBase",
    "VehicleCreate",
    "Vehicle",
    "VehicleListResponse",
    "RoadSegmentTraffic",
    "CongestedSegment",
    "TrafficInformationResponse",
    "Coordinates",
    "RouteRequest",
    "RouteResponse",
]
