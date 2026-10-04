"""Traffic and vehicle management service.

Handles vehicle registration, telemetry ingestion, road-network association
via OSMnx and NetworkX, and dynamic traffic condition and congestion calculation.
"""
from collections import defaultdict
from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Optional, Tuple

import osmnx as ox

from app.core.config import settings
from app.models.traffic import (
    CongestedSegment,
    RoadSegmentTraffic,
    TrafficInformationResponse,
)
from app.models.vehicle import (
    Vehicle,
    VehicleCreate,
    VehicleListResponse,
)
from app.services.osm_service import osm_graph_manager

logger = logging.getLogger(__name__)


# =====================================================================
# Domain Exceptions
# =====================================================================

class TrafficServiceError(Exception):
    """Base exception for traffic and vehicle service operations."""
    pass


class InvalidCoordinatesError(TrafficServiceError):
    """Raised when GPS coordinates are invalid or out of range."""
    pass


class RoadNetworkNotLoadedError(TrafficServiceError):
    """Raised when road association is attempted without an available road graph."""
    pass


class VehicleNotFoundError(TrafficServiceError):
    """Raised when querying a vehicle ID that is not registered."""
    pass


# =====================================================================
# Vehicle & Traffic Service Implementation
# =====================================================================

class VehicleTrafficService:
    """Thread-safe manager for vehicle telemetry and dynamic traffic conditions."""

    def __init__(self) -> None:
        self._vehicles: Dict[str, Vehicle] = {}
        self._lock = threading.Lock()

    def validate_coordinates(self, lat: float, lon: float) -> None:
        """Validate latitude and longitude ranges.

        Raises:
            InvalidCoordinatesError: If coordinates are out of standard GPS bounds or non-finite.
        """
        import math
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
            raise InvalidCoordinatesError(f"Coordinates must be numeric. Got lat={type(lat)}, lon={type(lon)}")

        if math.isnan(lat) or math.isinf(lat) or math.isnan(lon) or math.isinf(lon):
            raise InvalidCoordinatesError("Coordinates cannot be NaN or Infinite.")

        if not (-90.0 <= lat <= 90.0):
            raise InvalidCoordinatesError(
                f"Latitude {lat} is out of bounds. Must be between -90.0 and 90.0."
            )

        if not (-180.0 <= lon <= 180.0):
            raise InvalidCoordinatesError(
                f"Longitude {lon} is out of bounds. Must be between -180.0 and 180.0."
            )

    def validate_vehicle_payload(self, payload: VehicleCreate) -> None:
        """Validate vehicle telemetry payload fields."""
        self.validate_coordinates(payload.latitude, payload.longitude)
        if payload.speed < 0.0:
            raise InvalidCoordinatesError(f"Speed cannot be negative: {payload.speed}")
        if payload.heading is not None and not (0.0 <= payload.heading <= 360.0):
            raise InvalidCoordinatesError(f"Heading must be between 0.0 and 360.0: {payload.heading}")


    def associate_vehicle_with_network(
        self,
        lat: float,
        lon: float,
    ) -> Tuple[int, Tuple[int, int, int], Optional[str]]:
        """Associate GPS position with nearest OSM road node, edge, and road name.

        Returns:
            Tuple of (nearest_node_id, (u, v, key), road_name_or_description)

        Raises:
            InvalidCoordinatesError: If coordinates are out of range.
            RoadNetworkNotLoadedError: If the road network cannot be accessed.
        """
        self.validate_coordinates(lat, lon)

        # Retrieve in-memory OSM graph or trigger download
        graph = osm_graph_manager.get_in_memory_graph()
        if graph is None:
            logger.info("OSM graph not loaded; loading road network for '%s'...", settings.OSM_LOCATION)
            osm_graph_manager.get_road_network()
            graph = osm_graph_manager.get_in_memory_graph()

        if graph is None:
            raise RoadNetworkNotLoadedError(
                f"Failed to load OSM road network for '{settings.OSM_LOCATION}'"
            )

        try:
            # OSMnx uses X=longitude, Y=latitude
            raw_node = ox.nearest_nodes(graph, X=lon, Y=lat)
            nearest_node = int(raw_node)

            raw_edge = ox.nearest_edges(graph, X=lon, Y=lat)
            u, v, k = int(raw_edge[0]), int(raw_edge[1]), int(raw_edge[2])
            nearest_edge = (u, v, k)

            # Determine road name from edge attributes
            road_name: Optional[str] = None
            if graph.has_edge(u, v, k):
                edge_data = graph[u][v][k]
                name_attr = edge_data.get("name")
                if isinstance(name_attr, list):
                    road_name = ", ".join(str(n) for n in name_attr if n)
                elif name_attr:
                    road_name = str(name_attr)
                else:
                    highway = edge_data.get("highway", "road")
                    if isinstance(highway, list):
                        highway = "/".join(str(h) for h in highway)
                    road_name = f"Unnamed {highway} ({u} -> {v})"
            else:
                road_name = f"Road segment ({u} -> {v})"

            return nearest_node, nearest_edge, road_name

        except Exception as exc:
            logger.error("Error associating coordinates (%f, %f) with OSM graph: %s", lat, lon, exc)
            raise TrafficServiceError(
                f"Failed to associate position with road network: {exc}"
            ) from exc

    def register_vehicle(self, payload: VehicleCreate) -> Vehicle:
        """Register or update a vehicle's telemetry with real OSM road association.

        Args:
            payload: VehicleCreate schema containing position and telemetry.

        Returns:
            Vehicle instance with assigned nearest node, edge, and road information.
        """
        self.validate_vehicle_payload(payload)

        nearest_node, nearest_edge, road_name = self.associate_vehicle_with_network(
            lat=payload.latitude,
            lon=payload.longitude,
        )

        vehicle = Vehicle(
            vehicle_id=payload.vehicle_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            speed=payload.speed,
            vehicle_type=payload.vehicle_type,
            heading=payload.heading,
            nearest_node=nearest_node,
            nearest_edge=nearest_edge,
            current_road=road_name,
            updated_at=datetime.now(timezone.utc),
        )

        with self._lock:
            self._vehicles[vehicle.vehicle_id] = vehicle
            logger.info(
                "Registered vehicle '%s' at (%f, %f) on '%s' (node=%d, edge=%s, speed=%.1f km/h).",
                vehicle.vehicle_id,
                vehicle.latitude,
                vehicle.longitude,
                vehicle.current_road,
                vehicle.nearest_node,
                vehicle.nearest_edge,
                vehicle.speed,
            )

        return vehicle

    def get_all_vehicles(self) -> List[Vehicle]:
        """Return a snapshot list of all currently registered vehicles."""
        with self._lock:
            return list(self._vehicles.values())

    def get_vehicle_list_response(self) -> VehicleListResponse:
        """Return VehicleListResponse with total count and vehicle list."""
        vehicles = self.get_all_vehicles()
        return VehicleListResponse(total=len(vehicles), vehicles=vehicles)

    def get_vehicle(self, vehicle_id: str) -> Optional[Vehicle]:
        """Retrieve a registered vehicle by ID."""
        with self._lock:
            return self._vehicles.get(vehicle_id)

    def clear_vehicles(self) -> None:
        """Clear all registered vehicles (used for testing or resetting session)."""
        with self._lock:
            self._vehicles.clear()

    def calculate_traffic_conditions(self) -> TrafficInformationResponse:
        """Calculate dynamic traffic conditions and congestion based on registered vehicles.

        Uses configurable thresholds from settings:
        - TRAFFIC_FREE_FLOW_SPEED_MIN
        - TRAFFIC_CONGESTION_SPEED_MAX
        - SEGMENT_CONGESTION_VEHICLE_THRESHOLD
        - TRAFFIC_DENSITY_HIGH_THRESHOLD
        - TRAFFIC_DENSITY_MODERATE_THRESHOLD
        """
        vehicles = self.get_all_vehicles()
        total_vehicles = len(vehicles)

        # Baseline empty state
        if total_vehicles == 0:
            return TrafficInformationResponse(
                location=settings.OSM_LOCATION,
                status="idle",
                total_vehicles=0,
                average_speed=0.0,
                traffic_density=0.0,
                overall_condition="free_flow",
                vehicles_per_road_segment={},
                congested_segments=[],
                road_segments=[],
                timestamp=datetime.now(timezone.utc),
            )

        # 1. System-wide average speed
        total_speed = sum(v.speed for v in vehicles)
        system_avg_speed = round(total_speed / total_vehicles, 2)

        # 2. Group vehicles by nearest edge
        edge_groups: Dict[str, List[Vehicle]] = defaultdict(list)
        for v in vehicles:
            if v.nearest_edge:
                edge_key = f"{v.nearest_edge[0]}_{v.nearest_edge[1]}_{v.nearest_edge[2]}"
            elif v.nearest_node:
                edge_key = f"node_{v.nearest_node}"
            else:
                edge_key = "unassigned_segment"
            edge_groups[edge_key].append(v)

        road_segments: List[RoadSegmentTraffic] = []
        congested_segments: List[CongestedSegment] = []
        vehicles_per_road_segment: Dict[str, int] = {}

        for edge_id, v_list in edge_groups.items():
            count = len(v_list)
            vehicles_per_road_segment[edge_id] = count
            seg_avg_speed = round(sum(v.speed for v in v_list) / count, 2)
            road_name = v_list[0].current_road

            # Determine segment condition based on configurable thresholds
            is_congested_by_count = count >= settings.SEGMENT_CONGESTION_VEHICLE_THRESHOLD
            is_congested_by_speed = seg_avg_speed <= settings.TRAFFIC_CONGESTION_SPEED_MAX

            if is_congested_by_count or is_congested_by_speed:
                congestion_level = "congested"
                reasons = []
                if is_congested_by_count:
                    reasons.append(
                        f"Vehicle count ({count}) exceeds threshold ({settings.SEGMENT_CONGESTION_VEHICLE_THRESHOLD})"
                    )
                if is_congested_by_speed:
                    reasons.append(
                        f"Avg speed ({seg_avg_speed} km/h) below threshold ({settings.TRAFFIC_CONGESTION_SPEED_MAX} km/h)"
                    )
                congested_segments.append(
                    CongestedSegment(
                        edge_id=edge_id,
                        road_name=road_name,
                        vehicle_count=count,
                        average_speed=seg_avg_speed,
                        reason="; ".join(reasons),
                    )
                )
            elif seg_avg_speed >= settings.TRAFFIC_FREE_FLOW_SPEED_MIN:
                congestion_level = "free_flow"
            else:
                congestion_level = "moderate"

            road_segments.append(
                RoadSegmentTraffic(
                    edge_id=edge_id,
                    road_name=road_name,
                    vehicle_count=count,
                    average_speed=seg_avg_speed,
                    congestion_level=congestion_level,
                )
            )

        # 3. Traffic Density (vehicles per active road segment)
        active_segments_count = len(edge_groups)
        traffic_density = round(total_vehicles / max(1, active_segments_count), 2)

        # 4. Overall Traffic Condition
        if len(congested_segments) > 0 or system_avg_speed <= settings.TRAFFIC_CONGESTION_SPEED_MAX:
            overall_condition = "congested"
        elif (
            system_avg_speed >= settings.TRAFFIC_FREE_FLOW_SPEED_MIN
            and traffic_density <= settings.TRAFFIC_DENSITY_MODERATE_THRESHOLD
        ):
            overall_condition = "free_flow"
        else:
            overall_condition = "moderate"

        return TrafficInformationResponse(
            location=settings.OSM_LOCATION,
            status="active",
            total_vehicles=total_vehicles,
            average_speed=system_avg_speed,
            traffic_density=traffic_density,
            overall_condition=overall_condition,
            vehicles_per_road_segment=vehicles_per_road_segment,
            congested_segments=congested_segments,
            road_segments=road_segments,
            timestamp=datetime.now(timezone.utc),
        )


# Global singleton instance
traffic_service = VehicleTrafficService()
