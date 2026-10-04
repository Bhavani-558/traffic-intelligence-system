"""Routing service for Flowline Traffic Optimization System.

Calculates real shortest-path routes on the OpenStreetMap road network graph
using NetworkX and OSMnx. Supports distance-based and travel-time-based routing.
"""
import logging
import math
import threading
from typing import List, Optional, Tuple

import networkx as nx
import osmnx as ox

from app.core.config import settings
from app.models.route import Coordinates, RouteRequest, RouteResponse
from app.services.osm_service import calculate_graph_bounds, osm_graph_manager

logger = logging.getLogger(__name__)


# =====================================================================
# Domain Exceptions
# =====================================================================

class RoutingError(Exception):
    """Base exception for routing operations."""
    pass


class InvalidRouteCoordinatesError(RoutingError):
    """Raised when origin or destination coordinates are out of standard GPS bounds."""
    pass


class CoordinatesOutsideBoundsError(RoutingError):
    """Raised when coordinates fall outside the road network coverage area."""
    pass


class NoRouteFoundError(RoutingError):
    """Raised when no navigable path connects origin and destination nodes."""
    pass


class GraphNotAvailableError(RoutingError):
    """Raised when the road network graph cannot be retrieved or loaded."""
    pass


# =====================================================================
# Routing Service Implementation
# =====================================================================

class RoutingService:
    """Calculates shortest paths and optimal routes over the real OSM road network."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._speeds_added = False

    def validate_coordinates(self, lat: float, lon: float, point_label: str = "Coordinate") -> None:
        """Verify that latitude and longitude are valid finite GPS numbers.

        Raises:
            InvalidRouteCoordinatesError: If out of range or non-finite.
        """
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
            raise InvalidRouteCoordinatesError(
                f"{point_label} coordinates must be numeric. Got lat={type(lat)}, lon={type(lon)}"
            )

        if math.isnan(lat) or math.isinf(lat) or math.isnan(lon) or math.isinf(lon):
            raise InvalidRouteCoordinatesError(f"{point_label} coordinates cannot be NaN or Infinite.")

        if not (-90.0 <= lat <= 90.0):
            raise InvalidRouteCoordinatesError(
                f"{point_label} latitude {lat} is out of bounds. Must be between -90.0 and 90.0."
            )

        if not (-180.0 <= lon <= 180.0):
            raise InvalidRouteCoordinatesError(
                f"{point_label} longitude {lon} is out of bounds. Must be between -180.0 and 180.0."
            )

    def check_within_coverage_bounds(
        self,
        lat: float,
        lon: float,
        graph: nx.MultiDiGraph,
        point_label: str = "Point",
        margin_degrees: float = 0.08,  # ~8.8 km buffer around city perimeter
    ) -> None:
        """Verify that coordinates lie within the loaded road network's coverage area.

        Raises:
            CoordinatesOutsideBoundsError: If outside network bounds.
        """
        bounds = calculate_graph_bounds(graph)
        min_lat = bounds["south"] - margin_degrees
        max_lat = bounds["north"] + margin_degrees
        min_lon = bounds["west"] - margin_degrees
        max_lon = bounds["east"] + margin_degrees

        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            raise CoordinatesOutsideBoundsError(
                f"{point_label} ({lat}, {lon}) is outside the available road network coverage area "
                f"for '{settings.OSM_LOCATION}' (latitude [{bounds['south']:.4f}, {bounds['north']:.4f}], "
                f"longitude [{bounds['west']:.4f}, {bounds['east']:.4f}])."
            )

    def _ensure_graph_enriched(self, graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
        """Ensure edge speeds and travel times are computed from OSM attributes."""
        with self._lock:
            # Check if any edge has travel_time
            has_travel_time = False
            for _, _, _, data in graph.edges(keys=True, data=True):
                if "travel_time" in data:
                    has_travel_time = True
                    break

            if not has_travel_time:
                try:
                    logger.info("Enriching road graph with edge speeds and travel times from OSM...")
                    graph = ox.add_edge_speeds(graph)
                    graph = ox.add_edge_travel_times(graph)
                except Exception as exc:
                    logger.warning("Failed to calculate edge travel times: %s", exc)

            return graph

    def calculate_shortest_route(self, request: RouteRequest) -> RouteResponse:
        """Calculate real shortest-path route on the OSM road network graph.

        Args:
            request: RouteRequest with origin, destination, and routing preference.

        Returns:
            RouteResponse containing node sequence, distance, travel time, and geometry.

        Raises:
            InvalidRouteCoordinatesError: If coordinates are out of valid GPS range.
            CoordinatesOutsideBoundsError: If coordinates fall outside the road network coverage.
            NoRouteFoundError: If no navigable path exists between origin and destination.
            GraphNotAvailableError: If OSM graph cannot be accessed.
        """
        # 1. Validate coordinates
        self.validate_coordinates(request.origin.latitude, request.origin.longitude, "Origin")
        self.validate_coordinates(request.destination.latitude, request.destination.longitude, "Destination")

        # 2. Access in-memory OSM road graph
        graph = osm_graph_manager.get_in_memory_graph()
        if graph is None:
            logger.info("Graph not loaded; loading road network for '%s'...", settings.OSM_LOCATION)
            osm_graph_manager.get_road_network()
            graph = osm_graph_manager.get_in_memory_graph()

        if graph is None or graph.number_of_nodes() == 0:
            raise GraphNotAvailableError(
                f"Road network graph is unavailable for '{settings.OSM_LOCATION}'."
            )

        # 3. Check bounding box coverage
        self.check_within_coverage_bounds(
            request.origin.latitude, request.origin.longitude, graph, "Origin"
        )
        self.check_within_coverage_bounds(
            request.destination.latitude, request.destination.longitude, graph, "Destination"
        )

        # 4. Ensure speed and travel time attributes exist on graph edges
        graph = self._ensure_graph_enriched(graph)

        # 5. Find nearest OSM road nodes to origin and destination
        try:
            raw_orig_node = ox.nearest_nodes(
                graph, X=request.origin.longitude, Y=request.origin.latitude
            )
            raw_dest_node = ox.nearest_nodes(
                graph, X=request.destination.longitude, Y=request.destination.latitude
            )
            orig_node = int(raw_orig_node)
            dest_node = int(raw_dest_node)
        except Exception as exc:
            logger.error("Failed to locate nearest nodes for origin/destination: %s", exc)
            raise RoutingError(f"Failed to locate nearest road nodes: {exc}") from exc

        # 6. Select routing criteria weight
        weight = "travel_time" if request.preference == "time" else "length"

        # 7. Calculate shortest path using NetworkX Dijkstra algorithm
        if orig_node == dest_node:
            route_nodes = [orig_node]
            total_distance_m = 0.0
            total_travel_time_s = 0.0
            road_names: List[str] = []
        else:
            try:
                route_nodes = nx.shortest_path(
                    graph,
                    source=orig_node,
                    target=dest_node,
                    weight=weight,
                )
                route_nodes = [int(n) for n in route_nodes]
            except nx.NetworkXNoPath as exc:
                raise NoRouteFoundError(
                    f"No navigable road route found between origin node {orig_node} and destination node {dest_node}."
                ) from exc
            except nx.NodeNotFound as exc:
                raise NoRouteFoundError(f"Routing node not found in graph: {exc}") from exc

            # Calculate accurate distance, travel time, and traversed street names
            total_distance_m = 0.0
            total_travel_time_s = 0.0
            road_names = []

            for u, v in zip(route_nodes[:-1], route_nodes[1:]):
                # Pick the edge with lowest weight between multi-edges
                if graph.has_edge(u, v):
                    edge_dict = graph[u][v]
                    best_edge_data = min(
                        edge_dict.values(),
                        key=lambda d: d.get(weight, float("inf")),
                    )
                    length_val = best_edge_data.get("length", 0.0)
                    total_distance_m += float(length_val)

                    tt_val = best_edge_data.get("travel_time")
                    if tt_val is not None:
                        total_travel_time_s += float(tt_val)
                    else:
                        # Fallback calculation if travel_time not present: assume 30 km/h (8.33 m/s)
                        total_travel_time_s += float(length_val) / 8.333

                    name_val = best_edge_data.get("name")
                    if isinstance(name_val, list):
                        for n in name_val:
                            if n and str(n) not in road_names:
                                road_names.append(str(n))
                    elif name_val and str(name_val) not in road_names:
                        road_names.append(str(name_val))

        # 8. Assemble route geometry coordinates
        route_coordinates = [
            Coordinates(
                latitude=float(graph.nodes[n]["y"]),
                longitude=float(graph.nodes[n]["x"]),
            )
            for n in route_nodes
        ]

        distance_km = round(total_distance_m / 1000.0, 3)
        travel_time_min = round(total_travel_time_s / 60.0, 2) if total_travel_time_s > 0 else 0.0

        logger.info(
            "Calculated route from %d to %d (%s): %d nodes, %.1f m (%.2f km), ~%.1f min.",
            orig_node,
            dest_node,
            request.preference,
            len(route_nodes),
            total_distance_m,
            distance_km,
            travel_time_min,
        )

        routing_method = "shortest_time" if request.preference == "time" else "shortest_distance"

        return RouteResponse(
            status="success",
            routing_method=routing_method,
            origin=request.origin,
            destination=request.destination,
            origin_node=orig_node,
            destination_node=dest_node,
            nearest_origin_node=orig_node,
            nearest_destination_node=dest_node,
            route_nodes=route_nodes,
            distance_meters=round(total_distance_m, 2),
            distance_km=distance_km,
            route_node_count=len(route_nodes),
            geometry=route_coordinates,
            route_coordinates=route_coordinates,
            estimated_travel_time_seconds=round(total_travel_time_s, 2),
            estimated_travel_time_minutes=travel_time_min,
            road_names=road_names,
            preference=request.preference,
        )


# Global singleton instance
routing_service = RoutingService()
