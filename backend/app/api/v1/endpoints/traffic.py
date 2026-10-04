"""Traffic endpoint router.

Provides endpoints for:
- GET /api/traffic: Dynamic traffic information based on active registered vehicles.
- GET /api/traffic/network: Real OpenStreetMap (OSM) road network graphs with node, edge, and boundary telemetry.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.models.traffic import (
    CongestedSegment,
    RoadSegmentTraffic,
    TrafficInformationResponse,
)
from app.services.osm_service import (
    OSMConnectionError,
    OSMDownloadError,
    OSMGraphLoadingError,
    OSMInvalidLocationError,
    osm_graph_manager,
)
from app.services.traffic_service import (
    RoadNetworkNotLoadedError,
    TrafficServiceError,
    traffic_service,
)

router = APIRouter()


class TrafficModuleStatus(BaseModel):
    module: str = "traffic"
    status: str = "initialized"
    message: str = "Traffic network and congestion monitoring module active."


class GeographicBounds(BaseModel):
    south: float = Field(..., description="Minimum latitude of road network bounds")
    north: float = Field(..., description="Maximum latitude of road network bounds")
    west: float = Field(..., description="Minimum longitude of road network bounds")
    east: float = Field(..., description="Maximum longitude of road network bounds")


class NetworkInfoResponse(BaseModel):
    location: str = Field(..., description="Geographical location query")
    nodes: int = Field(..., description="Actual number of nodes (intersections/junctions) in road graph")
    edges: int = Field(..., description="Actual number of drivable road segments/edges in road graph")
    status: str = Field("loaded", description="Graph load status")
    bounds: GeographicBounds = Field(..., description="Geographic bounding box coordinates")


@router.get(
    "",
    response_model=TrafficInformationResponse,
    summary="Get Current Traffic Information",
    description=(
        "Returns calculated traffic conditions based on currently registered vehicle data, "
        "including total vehicles, fleet average speed, vehicle counts per OSM road segment, "
        "traffic density, and congested segments based on configurable thresholds."
    ),
    responses={
        200: {"description": "Current traffic information retrieved successfully."},
        500: {"description": "Error computing traffic metrics."},
    },
)
@router.get(
    "/",
    response_model=TrafficInformationResponse,
    include_in_schema=False,
)
def get_traffic_information() -> TrafficInformationResponse:
    """Return current traffic conditions and metrics computed from vehicle data."""
    try:
        return traffic_service.calculate_traffic_conditions()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate traffic conditions: {str(exc)}",
        ) from exc


@router.get(
    "/status",
    response_model=TrafficModuleStatus,
    summary="Traffic Module Status",
    description="Endpoint for traffic module initialization status.",
)
def get_traffic_module_status() -> TrafficModuleStatus:
    """Return traffic module status."""
    return TrafficModuleStatus()


@router.get(
    "/network",
    response_model=NetworkInfoResponse,
    summary="Get Road Network Information",
    description=(
        "Retrieves real road network data downloaded from OpenStreetMap for the configured "
        "default location ('Vijayawada, Andhra Pradesh, India') or a specified custom location. "
        "Stores the graph in memory for reuse during the backend session."
    ),
    responses={
        200: {
            "description": "Road network loaded successfully with real node and edge counts.",
        },
        400: {"description": "Invalid location or no road network found for the query."},
        502: {"description": "OpenStreetMap / Overpass API download or server failure."},
        503: {"description": "Network or internet connectivity failure."},
        500: {"description": "Internal graph construction or loading failure."},
    },
)
def get_road_network(
    location: Optional[str] = Query(
        None,
        description="Optional custom location query. Defaults to configured OSM_LOCATION ('Vijayawada, Andhra Pradesh, India').",
    ),
    force_reload: bool = Query(
        False,
        description="Force re-downloading from OSM instead of utilizing the in-memory cached graph.",
    ),
) -> NetworkInfoResponse:
    """Download, cache in memory, and return real OSM road network statistics."""
    try:
        network_data = osm_graph_manager.get_road_network(
            location=location,
            force_reload=force_reload,
        )
        return NetworkInfoResponse(**network_data)

    except OSMInvalidLocationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid location: {str(exc)}",
        ) from exc

    except OSMConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Network connectivity error while contacting OpenStreetMap: {str(exc)}",
        ) from exc

    except OSMDownloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenStreetMap download error: {str(exc)}",
        ) from exc

    except OSMGraphLoadingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph loading error: {str(exc)}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error retrieving road network: {str(exc)}",
        ) from exc
