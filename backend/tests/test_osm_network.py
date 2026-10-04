"""Automated tests for OpenStreetMap (OSM) road network integration.

Tests configuration, graph download, NetworkX conversion, bounds calculation,
in-memory caching, error handling, and GET /api/traffic/network endpoint.
"""
import pytest
import networkx as nx
import httpx

from app.core.config import settings
from app.main import app
from app.services.osm_service import (
    OSMInvalidLocationError,
    calculate_graph_bounds,
    convert_to_networkx,
    extract_graph_metadata,
    osm_graph_manager,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_default_configuration():
    """Verify default OSM location and configuration settings."""
    assert settings.OSM_LOCATION == "Vijayawada, Andhra Pradesh, India"
    assert settings.OSM_NETWORK_TYPE == "drive"
    assert settings.OSM_CACHE_ENABLED is True


def test_convert_to_networkx():
    """Verify conversion of various graph types to NetworkX MultiDiGraph."""
    # Test DiGraph conversion
    dg = nx.DiGraph()
    dg.add_node(1, x=80.6, y=16.5)
    dg.add_node(2, x=80.61, y=16.51)
    dg.add_edge(1, 2, weight=1.5)
    converted = convert_to_networkx(dg)
    assert isinstance(converted, nx.MultiDiGraph)
    assert converted.number_of_nodes() == 2
    assert converted.number_of_edges() == 1


def test_calculate_graph_bounds():
    """Verify calculation of geographic bounds from node coordinates."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=80.55, y=16.45)
    G.add_node(2, x=80.65, y=16.55)
    bounds = calculate_graph_bounds(G)
    assert bounds["south"] == pytest.approx(16.45)
    assert bounds["north"] == pytest.approx(16.55)
    assert bounds["west"] == pytest.approx(80.55)
    assert bounds["east"] == pytest.approx(80.65)


def test_extract_graph_metadata():
    """Verify metadata extraction for a road graph."""
    G = nx.MultiDiGraph()
    G.add_node(1, x=80.55, y=16.45)
    G.add_node(2, x=80.65, y=16.55)
    G.add_edge(1, 2)
    meta = extract_graph_metadata(G, "Test City")
    assert meta["location"] == "Test City"
    assert meta["nodes"] == 2
    assert meta["edges"] == 1
    assert meta["status"] == "loaded"
    assert "bounds" in meta


def test_osm_invalid_location_error():
    """Verify that an unresolvable location raises OSMInvalidLocationError."""
    with pytest.raises(OSMInvalidLocationError):
        osm_graph_manager.get_road_network(
            location="NonExistentUnresolvableCity9999999XYZ",
            force_reload=True,
        )


@pytest.mark.anyio
async def test_api_traffic_network_endpoint_success():
    """Verify GET /api/traffic/network returns 200 OK with real OSM data."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/traffic/network")
        assert response.status_code == 200

        data = response.json()
        assert data["location"] == "Vijayawada, Andhra Pradesh, India"
        assert data["status"] == "loaded"
        assert isinstance(data["nodes"], int)
        assert data["nodes"] > 0
        assert isinstance(data["edges"], int)
        assert data["edges"] > 0

        # Bounds verification
        bounds = data["bounds"]
        assert bounds["south"] < bounds["north"]
        assert bounds["west"] < bounds["east"]

        # Verify in-memory caching is active
        assert osm_graph_manager.is_loaded() is True
        in_mem_graph = osm_graph_manager.get_in_memory_graph()
        assert in_mem_graph is not None
        assert in_mem_graph.number_of_nodes() == data["nodes"]
        assert in_mem_graph.number_of_edges() == data["edges"]


@pytest.mark.anyio
async def test_api_traffic_network_endpoint_invalid_location():
    """Verify GET /api/traffic/network with invalid location returns 400 Bad Request."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/traffic/network?location=NonExistentInvalidCity12345xyz")
        assert response.status_code == 400
        assert "Invalid location" in response.json().get("detail", "")


def test_road_network_service_exports():
    """Verify that backend/app/services/road_network.py correctly exposes services."""
    from app.services.road_network import (
        RoadNetworkManager,
        road_network_service,
        download_road_network,
        RoadNetworkError,
        RoadNetworkInvalidLocationError,
    )
    assert road_network_service is osm_graph_manager
    assert RoadNetworkManager is not None
    assert callable(download_road_network)
    assert issubclass(RoadNetworkInvalidLocationError, RoadNetworkError)

