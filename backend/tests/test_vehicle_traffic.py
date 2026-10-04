"""Automated tests for vehicle management, OSM road association, and traffic metrics.

Tests vehicle creation, coordinate validation, road/node association on real OSM graph,
vehicle listing, dynamic traffic metrics, and API endpoints.
"""
import pytest
import httpx

from app.core.config import settings
from app.main import app
from app.models.vehicle import VehicleCreate
from app.services.traffic_service import (
    InvalidCoordinatesError,
    traffic_service,
)
from app.services.osm_service import osm_graph_manager


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def clean_vehicle_store():
    """Ensure in-memory vehicle store is clean before and after each test."""
    traffic_service.clear_vehicles()
    yield
    traffic_service.clear_vehicles()


# =====================================================================
# Unit & Road Network Association Tests
# =====================================================================

def test_nearest_road_node_association_on_real_osm():
    """Verify that GPS coordinates in Vijayawada correctly associate with nearest OSM node and edge."""
    # Ensure real road graph is loaded
    osm_graph_manager.get_road_network()

    # M.G. Road / Benz Circle area in Vijayawada
    lat, lon = 16.5062, 80.6480
    node, edge, road_name = traffic_service.associate_vehicle_with_network(lat, lon)

    assert isinstance(node, int)
    assert node > 0
    assert isinstance(edge, tuple)
    assert len(edge) == 3
    assert isinstance(edge[0], int)
    assert isinstance(edge[1], int)
    assert isinstance(edge[2], int)
    assert road_name is not None
    assert isinstance(road_name, str)
    assert len(road_name) > 0


def test_invalid_coordinates_validation():
    """Verify that invalid GPS coordinates raise InvalidCoordinatesError."""
    # Latitude > 90
    with pytest.raises(InvalidCoordinatesError):
        traffic_service.validate_coordinates(91.0, 80.0)

    # Latitude < -90
    with pytest.raises(InvalidCoordinatesError):
        traffic_service.validate_coordinates(-95.0, 80.0)

    # Longitude > 180
    with pytest.raises(InvalidCoordinatesError):
        traffic_service.validate_coordinates(16.5, 185.0)

    # Longitude < -180
    with pytest.raises(InvalidCoordinatesError):
        traffic_service.validate_coordinates(16.5, -190.0)

    # Non-finite coordinates
    with pytest.raises(InvalidCoordinatesError):
        traffic_service.validate_coordinates(float("nan"), 80.0)


# =====================================================================
# Traffic Metric Calculation Tests
# =====================================================================

def test_traffic_metrics_empty():
    """Verify traffic metrics when no vehicles are registered."""
    metrics = traffic_service.calculate_traffic_conditions()
    assert metrics.total_vehicles == 0
    assert metrics.average_speed == 0.0
    assert metrics.traffic_density == 0.0
    assert metrics.overall_condition == "free_flow"
    assert metrics.congested_segments == []
    assert metrics.road_segments == []
    assert metrics.status == "idle"


def test_traffic_metrics_free_flow():
    """Verify free-flow classification when vehicles move at speeds above free-flow threshold."""
    # Register two vehicles at high speeds at different coordinates
    traffic_service.register_vehicle(
        VehicleCreate(
            vehicle_id="fast-1",
            latitude=16.5062,
            longitude=80.6480,
            speed=50.0,
            vehicle_type="car",
        )
    )
    traffic_service.register_vehicle(
        VehicleCreate(
            vehicle_id="fast-2",
            latitude=16.5150,
            longitude=80.6320,
            speed=60.0,
            vehicle_type="car",
        )
    )

    metrics = traffic_service.calculate_traffic_conditions()
    assert metrics.total_vehicles == 2
    assert metrics.average_speed == 55.0
    assert metrics.overall_condition == "free_flow"
    assert len(metrics.congested_segments) == 0
    assert metrics.status == "active"


def test_traffic_metrics_congested_by_speed():
    """Verify congestion detection when vehicle speeds drop below congestion threshold."""
    traffic_service.register_vehicle(
        VehicleCreate(
            vehicle_id="slow-1",
            latitude=16.5062,
            longitude=80.6480,
            speed=12.0,  # Below TRAFFIC_CONGESTION_SPEED_MAX (20.0 km/h)
            vehicle_type="bus",
        )
    )

    metrics = traffic_service.calculate_traffic_conditions()
    assert metrics.total_vehicles == 1
    assert metrics.average_speed == 12.0
    assert metrics.overall_condition == "congested"
    assert len(metrics.congested_segments) == 1
    assert "below threshold" in metrics.congested_segments[0].reason


def test_traffic_metrics_congested_by_vehicle_count():
    """Verify congestion detection when vehicle count on an edge meets or exceeds threshold."""
    # Register 3 vehicles at the exact same position (meeting SEGMENT_CONGESTION_VEHICLE_THRESHOLD=3)
    for i in range(1, 4):
        traffic_service.register_vehicle(
            VehicleCreate(
                vehicle_id=f"cluster-{i}",
                latitude=16.5062,
                longitude=80.6480,
                speed=30.0,  # Moderate speed, but cluster density triggers congestion
                vehicle_type="car",
            )
        )

    metrics = traffic_service.calculate_traffic_conditions()
    assert metrics.total_vehicles == 3
    assert len(metrics.congested_segments) >= 1
    assert metrics.overall_condition == "congested"
    assert any("exceeds threshold" in seg.reason for seg in metrics.congested_segments)


# =====================================================================
# HTTP API Endpoint Tests
# =====================================================================

@pytest.mark.anyio
async def test_vehicle_creation_api():
    """Verify POST /api/vehicles registers a vehicle and associates OSM road data."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        payload = {
            "vehicle_id": "veh-101",
            "latitude": 16.5062,
            "longitude": 80.6480,
            "speed": 35.5,
            "vehicle_type": "car",
            "heading": 180.0,
        }
        response = await client.post("/api/vehicles", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["vehicle_id"] == "veh-101"
        assert data["latitude"] == 16.5062
        assert data["longitude"] == 80.6480
        assert data["speed"] == 35.5
        assert data["vehicle_type"] == "car"
        assert data["heading"] == 180.0
        assert data["nearest_node"] is not None
        assert isinstance(data["nearest_node"], int)
        assert data["nearest_edge"] is not None
        assert len(data["nearest_edge"]) == 3
        assert data["current_road"] is not None


@pytest.mark.anyio
async def test_vehicle_creation_invalid_coordinates():
    """Verify POST /api/vehicles rejects invalid coordinates with 400 Bad Request."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Latitude out of bounds
        payload = {
            "vehicle_id": "veh-invalid-lat",
            "latitude": 999.0,
            "longitude": 80.6480,
            "speed": 25.0,
        }
        response = await client.post("/api/vehicles", json=payload)
        assert response.status_code == 400
        assert "Invalid coordinates" in response.json().get("detail", "")

        # Longitude out of bounds
        payload = {
            "vehicle_id": "veh-invalid-lon",
            "latitude": 16.5062,
            "longitude": -250.0,
            "speed": 25.0,
        }
        response = await client.post("/api/vehicles", json=payload)
        assert response.status_code == 400
        assert "Invalid coordinates" in response.json().get("detail", "")

        # Negative speed
        payload = {
            "vehicle_id": "veh-invalid-speed",
            "latitude": 16.5062,
            "longitude": 80.6480,
            "speed": -10.0,
        }
        response = await client.post("/api/vehicles", json=payload)
        assert response.status_code == 400
        assert "Speed cannot be negative" in response.json().get("detail", "")


@pytest.mark.anyio
async def test_vehicle_listing_api():
    """Verify GET /api/vehicles returns all registered vehicles."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Initially empty
        res = await client.get("/api/vehicles")
        assert res.status_code == 200
        assert res.json()["total"] == 0
        assert res.json()["vehicles"] == []

        # Add two vehicles
        await client.post(
            "/api/vehicles",
            json={
                "vehicle_id": "v-1",
                "latitude": 16.5062,
                "longitude": 80.6480,
                "speed": 28.0,
            },
        )
        await client.post(
            "/api/vehicles",
            json={
                "vehicle_id": "v-2",
                "latitude": 16.5150,
                "longitude": 80.6320,
                "speed": 42.0,
            },
        )

        res = await client.get("/api/vehicles")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        assert len(data["vehicles"]) == 2
        ids = [v["vehicle_id"] for v in data["vehicles"]]
        assert "v-1" in ids
        assert "v-2" in ids


@pytest.mark.anyio
async def test_traffic_endpoint_api():
    """Verify GET /api/traffic returns computed metrics from registered vehicle data."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Add realistic vehicle test fixtures
        await client.post(
            "/api/vehicles",
            json={
                "vehicle_id": "v-benz-1",
                "latitude": 16.5062,
                "longitude": 80.6480,
                "speed": 40.0,
                "vehicle_type": "car",
            },
        )
        await client.post(
            "/api/vehicles",
            json={
                "vehicle_id": "v-gov-2",
                "latitude": 16.5150,
                "longitude": 80.6320,
                "speed": 30.0,
                "vehicle_type": "bus",
            },
        )

        res = await client.get("/api/traffic")
        assert res.status_code == 200
        data = res.json()

        assert data["location"] == settings.OSM_LOCATION
        assert data["status"] == "active"
        assert data["total_vehicles"] == 2
        assert data["average_speed"] == 35.0  # (40 + 30) / 2
        assert isinstance(data["traffic_density"], float)
        assert data["overall_condition"] in ("free_flow", "moderate", "congested")
        assert isinstance(data["vehicles_per_road_segment"], dict)
        assert len(data["vehicles_per_road_segment"]) >= 1
        assert isinstance(data["road_segments"], list)
        assert len(data["road_segments"]) >= 1
