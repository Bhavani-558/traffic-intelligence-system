from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.api import api_router


def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        description="Production-ready FastAPI backend foundation for Flowline Traffic Optimization System.",
    )

    # Configure CORS middleware
    allow_credentials = "*" not in settings.BACKEND_CORS_ORIGINS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router with prefix /api
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/", tags=["root"], summary="Root Service Information")
    def root():
        """Root endpoint with service metadata and documentation links."""
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
            "health": f"{settings.API_V1_STR}/health",
        }

    return application


app = create_application()
