"""Vehicles endpoint router.

Provides endpoints for vehicle registration, real OSM road-network association,
and telemetry retrieval.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, status

from app.models.vehicle import (
    Vehicle,
    VehicleCreate,
    VehicleListResponse,
)
from app.services.traffic_service import (
    InvalidCoordinatesError,
    RoadNetworkNotLoadedError,
    TrafficServiceError,
    traffic_service,
)

router = APIRouter()


@router.get(
    "",
    response_model=VehicleListResponse,
    summary="List Registered Vehicles",
    description="Returns all currently active registered vehicles with their associated OSM road nodes and edges.",
    responses={
        200: {"description": "List of registered vehicles retrieved successfully."},
    },
)
@router.get(
    "/",
    response_model=VehicleListResponse,
    include_in_schema=False,
)
def get_vehicles() -> VehicleListResponse:
    """Return the currently registered vehicles."""
    return traffic_service.get_vehicle_list_response()


@router.post(
    "",
    response_model=Vehicle,
    status_code=status.HTTP_201_CREATED,
    summary="Register / Update Vehicle Position",
    description=(
        "Registers a new vehicle or updates an existing vehicle's position, "
        "associating coordinates with the nearest OpenStreetMap road network node and edge."
    ),
    responses={
        201: {"description": "Vehicle registered successfully with OSM road association."},
        400: {"description": "Invalid coordinates or vehicle payload."},
        503: {"description": "OSM road network unavailable or not loaded."},
        500: {"description": "Internal vehicle processing error."},
    },
)
@router.post(
    "/",
    response_model=Vehicle,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def register_vehicle(payload: VehicleCreate) -> Vehicle:
    """Register or update a vehicle with real OSM road association."""
    try:
        vehicle = traffic_service.register_vehicle(payload)
        return vehicle

    except InvalidCoordinatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid coordinates or vehicle parameters: {str(exc)}",
        ) from exc

    except RoadNetworkNotLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Road network unavailable: {str(exc)}",
        ) from exc

    except TrafficServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vehicle service error: {str(exc)}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error registering vehicle: {str(exc)}",
        ) from exc


@router.get(
    "/{vehicle_id}",
    response_model=Vehicle,
    summary="Get Vehicle by ID",
    description="Retrieves a registered vehicle by its unique vehicle ID.",
    responses={
        200: {"description": "Vehicle telemetry retrieved successfully."},
        404: {"description": "Vehicle not found."},
    },
)
def get_vehicle_by_id(
    vehicle_id: str = Path(..., description="Unique vehicle identifier"),
) -> Vehicle:
    """Retrieve a single registered vehicle."""
    vehicle = traffic_service.get_vehicle(vehicle_id)
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found.",
        )
    return vehicle


@router.delete(
    "",
    summary="Clear All Registered Vehicles",
    description="Clears all registered vehicle records (useful for test resets).",
    status_code=status.HTTP_200_OK,
)
def clear_all_vehicles():
    """Clear all registered vehicles from the in-memory store."""
    traffic_service.clear_vehicles()
    return {"status": "cleared", "message": "All registered vehicles have been cleared."}
