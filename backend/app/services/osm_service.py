"""OpenStreetMap (OSM) Road Network Service.

Handles downloading, validating, in-memory caching, and metadata extraction
for drivable road network graphs using OSMnx and NetworkX.
"""
import logging
import threading
from typing import Any, Dict, Optional, Tuple

import networkx as nx
import osmnx as ox
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


# =====================================================================
# Domain Exceptions for Robust Error Handling
# =====================================================================

class OSMError(Exception):
    """Base exception for all OSM road network operations."""
    pass


class OSMInvalidLocationError(OSMError):
    """Raised when an invalid or unresolvable location is supplied."""
    pass


class OSMConnectionError(OSMError):
    """Raised when network/internet connectivity issues prevent fetching OSM data."""
    pass


class OSMDownloadError(OSMError):
    """Raised when the OpenStreetMap / Overpass API encounters an error or rate limit."""
    pass


class OSMGraphLoadingError(OSMError):
    """Raised when graph construction or NetworkX conversion fails."""
    pass


# =====================================================================
# Core Graph Operations
# =====================================================================

def convert_to_networkx(graph: Any) -> nx.MultiDiGraph:
    """Ensure the graph is a valid NetworkX MultiDiGraph instance.

    Converts or validates the graph structure as needed.
    """
    if isinstance(graph, nx.MultiDiGraph):
        return graph
    elif isinstance(graph, (nx.DiGraph, nx.Graph)):
        return nx.MultiDiGraph(graph)
    elif hasattr(graph, "to_directed"):
        return nx.MultiDiGraph(graph.to_directed())
    else:
        try:
            return nx.MultiDiGraph(graph)
        except Exception as exc:
            raise OSMGraphLoadingError(
                f"Failed to convert graph of type {type(graph).__name__} to NetworkX MultiDiGraph: {exc}"
            ) from exc


def calculate_graph_bounds(graph: nx.MultiDiGraph) -> Dict[str, float]:
    """Extract geographic bounding box (south, north, west, east) from graph nodes.

    Returns:
        dict with keys 'south', 'north', 'west', 'east' containing float coordinates.
    """
    if not graph or graph.number_of_nodes() == 0:
        return {"south": 0.0, "north": 0.0, "west": 0.0, "east": 0.0}

    lats = [data["y"] for _, data in graph.nodes(data=True) if "y" in data]
    lons = [data["x"] for _, data in graph.nodes(data=True) if "x" in data]

    if not lats or not lons:
        return {"south": 0.0, "north": 0.0, "west": 0.0, "east": 0.0}

    return {
        "south": float(min(lats)),
        "north": float(max(lats)),
        "west": float(min(lons)),
        "east": float(max(lons)),
    }


def extract_graph_metadata(graph: nx.MultiDiGraph, location: str) -> Dict[str, Any]:
    """Extract basic graph information including node count, edge count, and bounds."""
    nx_graph = convert_to_networkx(graph)
    bounds = calculate_graph_bounds(nx_graph)

    return {
        "location": location,
        "nodes": nx_graph.number_of_nodes(),
        "edges": nx_graph.number_of_edges(),
        "status": "loaded",
        "bounds": bounds,
    }


def download_osm_graph(
    location: str,
    network_type: Optional[str] = None,
) -> nx.MultiDiGraph:
    """Download the drivable road network graph from OpenStreetMap.

    Args:
        location: Place name or geocodable address query.
        network_type: Filter for road types ('drive', 'drive_service', etc.).
                      Defaults to configured OSM_NETWORK_TYPE.

    Returns:
        A NetworkX MultiDiGraph representing the drivable road network.

    Raises:
        OSMInvalidLocationError: If the location is empty, unknown, or has no road network.
        OSMConnectionError: If network connectivity or timeout occurs.
        OSMDownloadError: If Overpass API returns a server error or rate limit.
        OSMGraphLoadingError: If graph conversion or processing fails.
    """
    if not location or not location.strip():
        raise OSMInvalidLocationError("Location cannot be empty.")

    target_loc = location.strip()
    target_net_type = network_type or settings.OSM_NETWORK_TYPE

    # Configure OSMnx settings
    ox.settings.use_cache = settings.OSM_CACHE_ENABLED
    ox.settings.log_console = False

    try:
        logger.info(
            "Querying OpenStreetMap road network for '%s' (network_type='%s')...",
            target_loc,
            target_net_type,
        )
        raw_graph = ox.graph_from_place(
            target_loc,
            network_type=target_net_type,
            simplify=True,
        )

        if raw_graph is None or len(raw_graph.nodes) == 0:
            raise OSMInvalidLocationError(
                f"No drivable road network found for location: '{target_loc}'"
            )

        # Convert/validate as NetworkX MultiDiGraph
        graph = convert_to_networkx(raw_graph)
        logger.info(
            "Successfully fetched graph for '%s': %d nodes, %d edges.",
            target_loc,
            graph.number_of_nodes(),
            graph.number_of_edges(),
        )
        return graph

    except (
        ox._errors.InsufficientResponseError,
        ox._errors.CacheOnlyInterruptError,
    ) as exc:
        logger.warning("OSM geocoder returned no results for '%s': %s", target_loc, exc)
        raise OSMInvalidLocationError(
            f"Invalid location '{target_loc}': Nominatim geocoder returned no results."
        ) from exc

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectTimeout,
    ) as exc:
        logger.error("Network connection failure while querying OSM for '%s': %s", target_loc, exc)
        raise OSMConnectionError(
            f"Network connectivity error while contacting OpenStreetMap: {exc}"
        ) from exc

    except (
        ox._errors.ResponseStatusCodeError,
        requests.exceptions.HTTPError,
    ) as exc:
        logger.error("OSM Overpass API response error for '%s': %s", target_loc, exc)
        raise OSMDownloadError(
            f"OpenStreetMap Overpass API server error: {exc}"
        ) from exc

    except ValueError as exc:
        err_msg = str(exc).lower()
        if "0 results" in err_msg or "no graph nodes" in err_msg or "no data" in err_msg or "polygon" in err_msg:
            logger.warning("No road network data found for '%s': %s", target_loc, exc)
            raise OSMInvalidLocationError(
                f"No drivable road network found for location '{target_loc}': {exc}"
            ) from exc
        logger.error("ValueError during OSM download for '%s': %s", target_loc, exc)
        raise OSMDownloadError(
            f"Failed to process road network for '{target_loc}': {exc}"
        ) from exc

    except OSMError:
        raise

    except Exception as exc:
        logger.error("Unexpected error loading OSM graph for '%s': %s", target_loc, exc, exc_info=True)
        raise OSMGraphLoadingError(
            f"Failed to download and construct road network graph: {exc}"
        ) from exc


# =====================================================================
# In-Memory Session Graph Manager
# =====================================================================

class OSMGraphManager:
    """Manages an in-memory session graph to avoid redundant OSM downloads."""

    def __init__(self) -> None:
        self._graph: Optional[nx.MultiDiGraph] = None
        self._location: Optional[str] = None
        self._metadata: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()

    def get_road_network(
        self,
        location: Optional[str] = None,
        force_reload: bool = False,
    ) -> Dict[str, Any]:
        """Retrieve road network metadata, using the in-memory cached graph when available.

        If the graph is not already loaded, or if location changes, or force_reload is True,
        it downloads the graph from OSM and stores it in memory.
        """
        target_location = (
            location.strip() if location and location.strip() else settings.OSM_LOCATION
        )

        with self._lock:
            # Check in-memory cache hit
            if (
                self._graph is not None
                and self._location == target_location
                and self._metadata is not None
                and not force_reload
            ):
                logger.info(
                    "Reusing in-memory OSM road graph for '%s' (%d nodes, %d edges).",
                    target_location,
                    self._metadata["nodes"],
                    self._metadata["edges"],
                )
                return dict(self._metadata)

            # Download fresh graph from OSM
            graph = download_osm_graph(
                target_location,
                network_type=settings.OSM_NETWORK_TYPE,
            )
            metadata = extract_graph_metadata(graph, target_location)

            # Cache in memory for backend session
            self._graph = graph
            self._location = target_location
            self._metadata = metadata

            logger.info(
                "Stored in-memory road graph for '%s': %d nodes, %d edges.",
                target_location,
                metadata["nodes"],
                metadata["edges"],
            )
            return dict(metadata)

    def get_in_memory_graph(self) -> Optional[nx.MultiDiGraph]:
        """Return the current in-memory NetworkX MultiDiGraph instance, if loaded."""
        with self._lock:
            return self._graph

    def get_current_location(self) -> Optional[str]:
        """Return the location string for the currently loaded in-memory graph."""
        with self._lock:
            return self._location

    def is_loaded(self) -> bool:
        """Check whether a road graph is currently loaded in memory."""
        with self._lock:
            return self._graph is not None

    def clear(self) -> None:
        """Clear the in-memory graph and cached metadata."""
        with self._lock:
            self._graph = None
            self._location = None
            self._metadata = None


# Global singleton instance
osm_graph_manager = OSMGraphManager()
