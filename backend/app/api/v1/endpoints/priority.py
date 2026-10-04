from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PriorityModuleStatus(BaseModel):
    module: str = "priority"
    status: str = "initialized"
    message: str = "Fleet weighting and emergency vehicle priority module placeholder."


@router.get(
    "",
    response_model=PriorityModuleStatus,
    summary="Priority Module Status",
    description="Placeholder endpoint for fleet priority weights, emergency green wave rules, and penalty calibration.",
)
@router.get(
    "/",
    response_model=PriorityModuleStatus,
    include_in_schema=False,
)
def get_priority_module_status() -> PriorityModuleStatus:
    return PriorityModuleStatus()
