"""Vehicle data models for Flowline Traffic Optimization System."""
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator


class VehicleBase(BaseModel):
    """Base schema for vehicle position and telemetry attributes."""
    vehicle_id: str = Field(
        ...,
        description="Unique vehicle identifier",
        min_length=1,
        max_length=100,
        examples=["veh-001"],
    )
    latitude: float = Field(
        ...,
        description="Current GPS latitude in decimal degrees",
        examples=[16.5062],
    )
    longitude: float = Field(
        ...,
        description="Current GPS longitude in decimal degrees",
        examples=[80.6480],
    )
    speed: float = Field(
        ...,
        description="Current speed in km/h",
        examples=[45.0],
    )
    vehicle_type: str = Field(
        default="car",
        description="Vehicle classification (e.g., car, bus, truck, motorcycle, emergency)",
        examples=["car"],
    )
    heading: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=360.0,
        description="Compass heading in degrees (0.0 to 360.0)",
        examples=[90.0],
    )

    @field_validator("vehicle_id")
    @classmethod
    def validate_vehicle_id(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("vehicle_id cannot be blank or whitespace only.")
        return stripped

    @field_validator("vehicle_type")
    @classmethod
    def validate_vehicle_type(cls, v: str) -> str:
        allowed = {"car", "bus", "truck", "motorcycle", "emergency", "van", "auto", "ambulance"}
        cleaned = v.strip().lower()
        if cleaned not in allowed:
            # Fall back to cleaned string if non-standard, or validate
            return cleaned or "car"
        return cleaned


class VehicleCreate(VehicleBase):
    """Request payload for registering or updating vehicle telemetry."""
    pass


class Vehicle(VehicleBase):
    """Registered vehicle model enriched with OSM road-network association."""
    nearest_node: Optional[int] = Field(
        default=None,
        description="Nearest OpenStreetMap intersection/junction node ID",
    )
    nearest_edge: Optional[Tuple[int, int, int]] = Field(
        default=None,
        description="Nearest OpenStreetMap road segment tuple (u, v, key)",
    )
    current_road: Optional[str] = Field(
        default=None,
        description="Name or description of the current road segment",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the latest position update",
    )


class VehicleListResponse(BaseModel):
    """Response containing currently registered vehicles."""
    total: int = Field(..., ge=0, description="Total count of active registered vehicles")
    vehicles: List[Vehicle] = Field(
        default_factory=list,
        description="List of registered vehicle telemetry objects",
    )
