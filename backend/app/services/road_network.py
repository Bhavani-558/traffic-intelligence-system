"""Road Network Service for Flowline Traffic Optimization System.

Provides high-level road network graph operations, leveraging OpenStreetMap (OSM)
via OSMnx and NetworkX. Re-exports and aliases core OSM graph loading, caching,
and validation functionality.
"""
from app.services.osm_service import (
    OSMError,
    OSMInvalidLocationError,
    OSMConnectionError,
    OSMDownloadError,
    OSMGraphLoadingError,
    convert_to_networkx,
    calculate_graph_bounds,
    extract_graph_metadata,
    download_osm_graph,
    OSMGraphManager,
    osm_graph_manager,
)

# Semantic aliases for road network operations
RoadNetworkError = OSMError
RoadNetworkInvalidLocationError = OSMInvalidLocationError
RoadNetworkConnectionError = OSMConnectionError
RoadNetworkDownloadError = OSMDownloadError
RoadNetworkGraphLoadingError = OSMGraphLoadingError

RoadNetworkManager = OSMGraphManager
road_network_service = osm_graph_manager

download_road_network = download_osm_graph

__all__ = [
    # Core exceptions
    "OSMError",
    "OSMInvalidLocationError",
    "OSMConnectionError",
    "OSMDownloadError",
    "OSMGraphLoadingError",
    "RoadNetworkError",
    "RoadNetworkInvalidLocationError",
    "RoadNetworkConnectionError",
    "RoadNetworkDownloadError",
    "RoadNetworkGraphLoadingError",
    # Functions
    "download_osm_graph",
    "download_road_network",
    "convert_to_networkx",
    "calculate_graph_bounds",
    "extract_graph_metadata",
    # Managers and singletons
    "OSMGraphManager",
    "osm_graph_manager",
    "RoadNetworkManager",
    "road_network_service",
]
