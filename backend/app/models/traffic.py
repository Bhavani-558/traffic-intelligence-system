"""Traffic condition and metric models for Flowline Traffic Optimization System."""
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RoadSegmentTraffic(BaseModel):
    """Calculated traffic information for a single road segment/edge."""
    edge_id: str = Field(
        ...,
        description="Road segment identifier in format 'u_v_key'",
    )
    road_name: Optional[str] = Field(
        default=None,
        description="Name of the street or road segment if identified from OSM",
    )
    vehicle_count: int = Field(
        ...,
        ge=0,
        description="Number of vehicles currently located on this road segment",
    )
    average_speed: float = Field(
        ...,
        ge=0.0,
        description="Average vehicle speed on this road segment in km/h",
    )
    congestion_level: str = Field(
        ...,
        description="Congestion classification: 'free_flow', 'moderate', or 'congested'",
    )


class CongestedSegment(BaseModel):
    """Details of a road segment flagged as congested."""
    edge_id: str = Field(..., description="Unique road segment identifier ('u_v_key')")
    road_name: Optional[str] = Field(default=None, description="Road or street name")
    vehicle_count: int = Field(..., ge=0, description="Number of vehicles on this segment")
    average_speed: float = Field(..., ge=0.0, description="Average speed on segment in km/h")
    reason: str = Field(..., description="Classification reason (e.g. low speed, high vehicle count)")


class TrafficInformationResponse(BaseModel):
    """Calculated traffic telemetry based on active registered vehicle data."""
    location: str = Field(
        ...,
        description="Configured geographical location for the road network",
    )
    status: str = Field(
        default="active",
        description="Traffic monitoring status ('active' or 'idle')",
    )
    total_vehicles: int = Field(
        ...,
        ge=0,
        description="Total number of currently registered vehicles",
    )
    average_speed: float = Field(
        ...,
        ge=0.0,
        description="Fleet-wide average speed across all active vehicles in km/h",
    )
    traffic_density: float = Field(
        ...,
        ge=0.0,
        description="Average vehicle density (vehicles per active road segment)",
    )
    overall_condition: str = Field(
        ...,
        description="Overall traffic status: 'free_flow', 'moderate', or 'congested'",
    )
    vehicles_per_road_segment: Dict[str, int] = Field(
        default_factory=dict,
        description="Mapping of road segment ID / name to vehicle count",
    )
    congested_segments: List[CongestedSegment] = Field(
        default_factory=list,
        description="List of road segments currently exceeding congestion thresholds",
    )
    road_segments: List[RoadSegmentTraffic] = Field(
        default_factory=list,
        description="Detailed per-segment traffic telemetry",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when traffic metrics were calculated",
    )
