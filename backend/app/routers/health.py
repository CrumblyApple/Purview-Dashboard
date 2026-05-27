from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str


class MessageResponse(BaseModel):
    message: str


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        service="purview-dashboard-api",
    )


@router.get("/hello", response_model=MessageResponse)
def hello(name: str = "World"):
    return MessageResponse(message=f"Hello, {name}!")
