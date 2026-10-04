from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Flowline Traffic Optimization System API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"
    SERVICE_NAME: str = "traffic-optimization-backend"

    # OpenStreetMap road network configuration
    OSM_LOCATION: str = "Vijayawada, Andhra Pradesh, India"
    OSM_NETWORK_TYPE: str = "drive"
    OSM_CACHE_ENABLED: bool = True

    # Configurable Traffic Classification Thresholds
    TRAFFIC_FREE_FLOW_SPEED_MIN: float = 40.0  # Speed >= 40 km/h considered free-flow
    TRAFFIC_CONGESTION_SPEED_MAX: float = 20.0  # Speed <= 20 km/h considered congested
    SEGMENT_CONGESTION_VEHICLE_THRESHOLD: int = 3  # Vehicles per segment triggering congestion
    TRAFFIC_DENSITY_HIGH_THRESHOLD: float = 2.0  # Vehicles/active segment considered high density
    TRAFFIC_DENSITY_MODERATE_THRESHOLD: float = 1.0  # Vehicles/active segment considered moderate


    # CORS origins: Next.js frontend dev & production addresses
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://traffic-optimization-system.onrender.com",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
