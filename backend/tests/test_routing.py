"""Automated tests for OpenStreetMap shortest-path routing layer.

Tests shortest-route calculation, distance and travel-time metrics, nearest-node lookup,
coordinate validation, bounding box checks, error handling, and API endpoints.
"""
import pytest
import httpx

from app.main import app
from app.models.route import Coordinates, RouteRequest
from app.services.osm_service import osm_graph_manager
from app.services.routing_service import (
    CoordinatesOutsideBoundsError,
    InvalidRouteCoordinatesError,
    routing_service,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module", autouse=True)
def ensure_osm_graph_loaded():
    """Ensure OSM road network graph is loaded once for all routing tests."""
    osm_graph_manager.get_road_network()


# =====================================================================
# Unit & Service Tests
# =====================================================================

def test_nearest_node_lookup_accuracy():
    """Verify nearest OSM node lookup for valid coordinates in Vijayawada."""
    G = osm_graph_manager.get_in_memory_graph()
    assert G is not None

    lat, lon = 16.5062, 80.6480
    import osmnx as ox
    node = ox.nearest_nodes(G, X=lon, Y=lat)
    assert int(node) in G.nodes
    node_data = G.nodes[node]
    assert "x" in node_data and "y" in node_data


def test_shortest_route_calculation_distance():
    """Verify shortest path route calculation using road length weight."""
    req = RouteRequest(
        origin=Coordinates(latitude=16.5062, longitude=80.6480),
        destination=Coordinates(latitude=16.5150, longitude=80.6320),
        preference="distance",
    )
    result = routing_service.calculate_shortest_route(req)

    assert result.status == "success"
    assert result.preference == "distance"
    assert result.nearest_origin_node > 0
    assert result.nearest_destination_node > 0
    assert len(result.route_nodes) > 1
    assert result.route_nodes[0] == result.nearest_origin_node
    assert result.route_nodes[-1] == result.nearest_destination_node
    assert result.distance_meters > 0.0
    assert result.distance_km == round(result.distance_meters / 1000.0, 3)
    assert len(result.route_coordinates) == len(result.route_nodes)
    assert isinstance(result.road_names, list)


def test_shortest_route_calculation_time():
    """Verify fastest route calculation using travel time weight."""
    req = RouteRequest(
        origin=Coordinates(latitude=16.5062, longitude=80.6480),
        destination=Coordinates(latitude=16.5150, longitude=80.6320),
        preference="time",
    )
    result = routing_service.calculate_shortest_route(req)

    assert result.status == "success"
    assert result.preference == "time"
    assert result.distance_meters > 0.0
    assert result.estimated_travel_time_seconds is not None
    assert result.estimated_travel_time_seconds > 0.0
    assert result.estimated_travel_time_minutes is not None
    assert result.estimated_travel_time_minutes > 0.0


def test_same_origin_and_destination():
    """Verify route calculation when origin and destination resolve to same node."""
    req = RouteRequest(
        origin=Coordinates(latitude=16.5062, longitude=80.6480),
        destination=Coordinates(latitude=16.5062, longitude=80.6480),
    )
    result = routing_service.calculate_shortest_route(req)

    assert result.distance_meters == 0.0
    assert result.distance_km == 0.0
    assert len(result.route_nodes) == 1
    assert len(result.route_coordinates) == 1


def test_invalid_coordinates_validation():
    """Verify that coordinates outside valid GPS bounds raise InvalidRouteCoordinatesError."""
    with pytest.raises(InvalidRouteCoordinatesError):
        routing_service.validate_coordinates(95.0, 80.6480)

    with pytest.raises(InvalidRouteCoordinatesError):
        routing_service.validate_coordinates(-95.0, 80.6480)

    with pytest.raises(InvalidRouteCoordinatesError):
        routing_service.validate_coordinates(16.5062, 190.0)

    with pytest.raises(InvalidRouteCoordinatesError):
        routing_service.validate_coordinates(float("nan"), 80.6480)


def test_coordinates_outside_coverage_bounds():
    """Verify that coordinates outside Vijayawada graph bounds raise CoordinatesOutsideBoundsError."""
    # Delhi coordinates
    delhi_coords = Coordinates(latitude=28.6139, longitude=77.2090)
    vja_coords = Coordinates(latitude=16.5062, longitude=80.6480)

    req = RouteRequest(origin=delhi_coords, destination=vja_coords)
    with pytest.raises(CoordinatesOutsideBoundsError):
        routing_service.calculate_shortest_route(req)

    req2 = RouteRequest(origin=vja_coords, destination=delhi_coords)
    with pytest.raises(CoordinatesOutsideBoundsError):
        routing_service.calculate_shortest_route(req2)


# =====================================================================
# API Endpoint Tests
# =====================================================================

@pytest.mark.anyio
async def test_api_shortest_route_endpoint_success():
    """Verify POST /api/routes/shortest returns 200 OK with real calculated route."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {
            "origin": {
                "latitude": 16.5062,
                "longitude": 80.6480,
            },
            "destination": {
                "latitude": 16.5150,
                "longitude": 80.6320,
            },
            "preference": "distance",
        }
        response = await client.post("/api/routes/shortest", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["preference"] == "distance"
        assert isinstance(data["nearest_origin_node"], int)
        assert isinstance(data["nearest_destination_node"], int)
        assert isinstance(data["route_nodes"], list)
        assert len(data["route_nodes"]) > 1
        assert data["distance_meters"] > 0.0
        assert data["distance_km"] > 0.0
        assert isinstance(data["route_coordinates"], list)
        assert len(data["route_coordinates"]) == len(data["route_nodes"])

        # Check first coordinate structure
        first_coord = data["route_coordinates"][0]
        assert "latitude" in first_coord
        assert "longitude" in first_coord


@pytest.mark.anyio
async def test_api_shortest_route_endpoint_outside_bounds():
    """Verify POST /api/routes/shortest rejects coordinates outside network area with 400."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {
            "origin": {
                "latitude": 12.9716,  # Bengaluru
                "longitude": 77.5946,
            },
            "destination": {
                "latitude": 16.5150,
                "longitude": 80.6320,
            },
        }
        response = await client.post("/api/routes/shortest", json=payload)
        assert response.status_code == 400
        assert "outside" in response.json().get("detail", "").lower()


@pytest.mark.anyio
async def test_api_routes_status_endpoint():
    """Verify GET /api/routes returns active status."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/routes")
        assert response.status_code == 200
        assert response.json()["status"] == "active"


def test_route_node_ordering_and_graph_continuity():
    """Verify that route nodes form a continuous navigable path on the OSM graph."""
    G = osm_graph_manager.get_in_memory_graph()
    assert G is not None

    req = RouteRequest(
        origin=Coordinates(latitude=16.5062, longitude=80.6480),
        destination=Coordinates(latitude=16.5150, longitude=80.6320),
        preference="distance",
    )
    result = routing_service.calculate_shortest_route(req)

    assert result.route_nodes[0] == result.origin_node
    assert result.route_nodes[-1] == result.destination_node
    assert result.route_node_count == len(result.route_nodes)

    # Verify edge connectivity for each consecutive node pair
    for u, v in zip(result.route_nodes[:-1], result.route_nodes[1:]):
        assert G.has_edge(u, v), f"Missing edge between {u} and {v} in calculated route path"


def test_route_distance_calculation_accuracy():
    """Verify that route distance accurately matches the sum of traversed edge lengths."""
    G = osm_graph_manager.get_in_memory_graph()
    assert G is not None

    req = RouteRequest(
        origin=Coordinates(latitude=16.5062, longitude=80.6480),
        destination=Coordinates(latitude=16.5150, longitude=80.6320),
        preference="distance",
    )
    result = routing_service.calculate_shortest_route(req)

    # Compute expected distance from graph edge attributes
    expected_dist = 0.0
    for u, v in zip(result.route_nodes[:-1], result.route_nodes[1:]):
        edge_dict = G[u][v]
        min_length = min(data.get("length", 0.0) for data in edge_dict.values())
        expected_dist += min_length

    assert round(result.distance_meters, 1) == round(expected_dist, 1)
    assert result.distance_km == round(result.distance_meters / 1000.0, 3)
    assert len(result.geometry) == result.route_node_count


@pytest.mark.anyio
async def test_api_shortest_time_endpoint_success():
    """Verify POST /api/routes/shortest-time calculates fastest route using OSM edge speeds."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {
            "origin": {
                "latitude": 16.5062,
                "longitude": 80.6480,
            },
            "destination": {
                "latitude": 16.5150,
                "longitude": 80.6320,
            },
        }
        response = await client.post("/api/routes/shortest-time", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["routing_method"] == "shortest_time"
        assert "origin" in data and "destination" in data
        assert isinstance(data["origin_node"], int)
        assert isinstance(data["destination_node"], int)
        assert isinstance(data["route_nodes"], list)
        assert data["route_node_count"] == len(data["route_nodes"])
        assert data["distance_meters"] > 0.0
        assert data["distance_km"] > 0.0
        assert data["estimated_travel_time_seconds"] > 0.0
        assert isinstance(data["geometry"], list)
        assert len(data["geometry"]) == data["route_node_count"]


@pytest.mark.anyio
async def test_api_shortest_route_prompt_example_structure():
    """Verify POST /api/routes/shortest response contains all prompt-specified fields."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {
            "origin": {
                "latitude": 16.5062,
                "longitude": 80.6480,
            },
            "destination": {
                "latitude": 16.5150,
                "longitude": 80.6320,
            },
        }
        response = await client.post("/api/routes/shortest", json=payload)
        assert response.status_code == 200

        data = response.json()
        # Verify required keys from task 4 prompt example structure
        expected_keys = [
            "status",
            "routing_method",
            "origin",
            "destination",
            "origin_node",
            "destination_node",
            "route_nodes",
            "distance_meters",
            "distance_km",
            "route_node_count",
            "geometry",
        ]
        for key in expected_keys:
            assert key in data, f"Missing required response key: '{key}'"

        assert data["status"] == "success"
        assert data["routing_method"] == "shortest_distance"
        assert data["origin"]["latitude"] == 16.5062
        assert data["origin"]["longitude"] == 80.6480
        assert data["destination"]["latitude"] == 16.5150
        assert data["destination"]["longitude"] == 80.6320
        assert isinstance(data["origin_node"], int)
        assert isinstance(data["destination_node"], int)
        assert isinstance(data["route_nodes"], list)
        assert data["route_node_count"] == len(data["route_nodes"])
        assert data["distance_meters"] > 0.0
        assert data["distance_km"] == round(data["distance_meters"] / 1000.0, 3)
        assert isinstance(data["geometry"], list)


@pytest.mark.anyio
async def test_no_route_found_handling(monkeypatch):
    """Verify that when no route exists between nodes, a 404 No Route Found is returned."""
    import networkx as nx

    def mock_shortest_path(*args, **kwargs):
        raise nx.NetworkXNoPath("No path found between nodes")

    monkeypatch.setattr(nx, "shortest_path", mock_shortest_path)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {
            "origin": {"latitude": 16.5062, "longitude": 80.6480},
            "destination": {"latitude": 16.5150, "longitude": 80.6320},
        }
        response = await client.post("/api/routes/shortest", json=payload)
        assert response.status_code == 404
        assert "no route found" in response.json().get("detail", "").lower()


@pytest.mark.anyio
async def test_graph_not_available_handling(monkeypatch):
    """Verify that when OSM graph is unavailable, a 503 Service Unavailable is returned."""
    monkeypatch.setattr(osm_graph_manager, "get_in_memory_graph", lambda: None)
    monkeypatch.setattr(osm_graph_manager, "get_road_network", lambda: None)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {
            "origin": {"latitude": 16.5062, "longitude": 80.6480},
            "destination": {"latitude": 16.5150, "longitude": 80.6320},
        }
        response = await client.post("/api/routes/shortest", json=payload)
        assert response.status_code == 503
        assert "unavailable" in response.json().get("detail", "").lower()

