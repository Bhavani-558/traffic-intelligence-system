"""Routes endpoint router.

Provides endpoints for shortest-path route calculation on the OpenStreetMap
road network and routing module telemetry.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.route import RouteRequest, RouteResponse
from app.services.routing_service import (
    CoordinatesOutsideBoundsError,
    GraphNotAvailableError,
    InvalidRouteCoordinatesError,
    NoRouteFoundError,
    RoutingError,
    routing_service,
)

router = APIRouter()


class RoutesModuleStatus(BaseModel):
    module: str = "routes"
    status: str = "active"
    message: str = "Route generation and shortest-path routing service active."


@router.get(
    "",
    response_model=RoutesModuleStatus,
    summary="Routes Module Status",
    description="Endpoint for routing module status and operational readiness.",
)
@router.get(
    "/",
    response_model=RoutesModuleStatus,
    include_in_schema=False,
)
def get_routes_module_status() -> RoutesModuleStatus:
    """Return routing module status."""
    return RoutesModuleStatus()


@router.post(
    "/shortest",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Real Shortest Route",
    description=(
        "Calculates an exact shortest path between origin and destination coordinates "
        "on the OpenStreetMap road network using NetworkX shortest-path algorithms. "
        "Supports routing by shortest distance or shortest travel time."
    ),
    responses={
        200: {"description": "Shortest route successfully computed on the road network."},
        400: {"description": "Invalid coordinates or coordinates outside coverage bounds."},
        404: {"description": "No navigable path connects the requested origin and destination."},
        503: {"description": "OSM road network graph is not available or failed to load."},
        500: {"description": "Internal routing computation failure."},
    },
)
def calculate_shortest_route(payload: RouteRequest) -> RouteResponse:
    """Calculate the shortest route between two geographic coordinates."""
    try:
        route_result = routing_service.calculate_shortest_route(payload)
        return route_result

    except InvalidRouteCoordinatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid coordinates: {str(exc)}",
        ) from exc

    except CoordinatesOutsideBoundsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Coordinates outside coverage area: {str(exc)}",
        ) from exc

    except NoRouteFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No route found: {str(exc)}",
        ) from exc

    except GraphNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Road network unavailable: {str(exc)}",
        ) from exc

    except RoutingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Routing service error: {str(exc)}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error calculating route: {str(exc)}",
        ) from exc


@router.post(
    "/shortest-time",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Fastest Route by OSM Travel Time",
    description=(
        "Calculates the fastest route between origin and destination coordinates "
        "on the OpenStreetMap road network using NetworkX and OSMnx edge travel times. "
        "Edge travel times are derived strictly from OSM road highway classifications and "
        "posted speed limits (maxspeed tags). This represents static OSM travel-time routing, "
        "NOT real-time dynamic traffic travel time."
    ),
    responses={
        200: {"description": "Fastest route successfully computed using OSM road travel times."},
        400: {"description": "Invalid coordinates or coordinates outside coverage bounds."},
        404: {"description": "No navigable path connects the requested origin and destination."},
        503: {"description": "OSM road network graph is not available or failed to load."},
        500: {"description": "Internal routing computation failure."},
    },
)
def calculate_shortest_time_route(payload: RouteRequest) -> RouteResponse:
    """Calculate the fastest route between two geographic coordinates using OSM travel times."""
    payload.preference = "time"
    try:
        route_result = routing_service.calculate_shortest_route(payload)
        return route_result

    except InvalidRouteCoordinatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid coordinates: {str(exc)}",
        ) from exc

    except CoordinatesOutsideBoundsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Coordinates outside coverage area: {str(exc)}",
        ) from exc

    except NoRouteFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No route found: {str(exc)}",
        ) from exc

    except GraphNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Road network unavailable: {str(exc)}",
        ) from exc

    except RoutingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Routing service error: {str(exc)}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error calculating route: {str(exc)}",
        ) from exc

