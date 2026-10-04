from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ZonesModuleStatus(BaseModel):
    module: str = "zones"
    status: str = "initialized"
    message: str = "Zonal clustering and parallel sub-graph decomposition module placeholder."


@router.get(
    "",
    response_model=ZonesModuleStatus,
    summary="Zones Module Status",
    description="Placeholder endpoint for urban zoning, graph partitioning, and distributed solving.",
)
@router.get(
    "/",
    response_model=ZonesModuleStatus,
    include_in_schema=False,
)
def get_zones_module_status() -> ZonesModuleStatus:
    return ZonesModuleStatus()
