"""Route request and response Pydantic models for Flowline Traffic Optimization System."""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Coordinates(BaseModel):
    """Geographic coordinate point (latitude, longitude)."""
    latitude: float = Field(
        ...,
        description="GPS latitude in decimal degrees (-90.0 to 90.0)",
        examples=[16.5062],
    )
    longitude: float = Field(
        ...,
        description="GPS longitude in decimal degrees (-180.0 to 180.0)",
        examples=[80.6480],
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude {v} is out of bounds. Must be between -90.0 and 90.0.")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude {v} is out of bounds. Must be between -180.0 and 180.0.")
        return v


class RouteRequest(BaseModel):
    """Request payload for shortest-path route calculation."""
    origin: Coordinates = Field(
        ...,
        description="Starting point coordinates",
    )
    destination: Coordinates = Field(
        ...,
        description="Ending point coordinates",
    )
    preference: str = Field(
        default="distance",
        description="Routing criteria: 'distance' (shortest path by road length) or 'time' (fastest path by travel time)",
        examples=["distance", "time"],
    )

    @field_validator("preference")
    @classmethod
    def validate_preference(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean in ("distance", "length", "shortest"):
            return "distance"
        elif clean in ("time", "travel_time", "fastest"):
            return "time"
        return "distance"


class RouteResponse(BaseModel):
    """Calculated shortest route on real OpenStreetMap road network."""
    status: str = Field(
        default="success",
        description="Route calculation status",
    )
    routing_method: str = Field(
        default="shortest_distance",
        description="Routing algorithm and metric applied ('shortest_distance' or 'shortest_time')",
    )
    origin: Coordinates = Field(..., description="Requested origin coordinate")
    destination: Coordinates = Field(..., description="Requested destination coordinate")
    origin_node: int = Field(
        ...,
        description="Nearest OpenStreetMap intersection/junction node ID to origin",
    )
    destination_node: int = Field(
        ...,
        description="Nearest OpenStreetMap intersection/junction node ID to destination",
    )
    nearest_origin_node: Optional[int] = Field(
        default=None,
        description="Nearest OpenStreetMap node ID to origin (backwards compatibility)",
    )
    nearest_destination_node: Optional[int] = Field(
        default=None,
        description="Nearest OpenStreetMap node ID to destination (backwards compatibility)",
    )
    route_nodes: List[int] = Field(
        ...,
        description="Ordered sequence of OpenStreetMap node IDs comprising the calculated route",
    )
    distance_meters: float = Field(
        ...,
        ge=0.0,
        description="Calculated total route distance in meters",
    )
    distance_km: float = Field(
        ...,
        ge=0.0,
        description="Calculated total route distance in kilometers",
    )
    route_node_count: int = Field(
        ...,
        ge=0,
        description="Total number of nodes along the calculated route",
    )
    geometry: List[Coordinates] = Field(
        ...,
        description="Ordered list of GPS coordinates along the route for mapping and geometry",
    )
    route_coordinates: Optional[List[Coordinates]] = Field(
        default=None,
        description="Ordered list of GPS coordinates along the route (backwards compatibility)",
    )
    estimated_travel_time_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Estimated travel duration in seconds based on OSM speed limits and road hierarchy",
    )
    estimated_travel_time_minutes: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Estimated travel duration in minutes",
    )
    road_names: List[str] = Field(
        default_factory=list,
        description="Distinct road or street names traversed along the route",
    )
    preference: str = Field(
        default="distance",
        description="Applied routing criteria ('distance' or 'time')",
    )
