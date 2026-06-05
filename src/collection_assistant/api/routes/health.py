"""Health check endpoint."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    database: str = "unknown"
    customer_count: int = 0


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """AC-008-08: includes database connectivity check and customer count."""
    from collection_assistant.db.session import db_session
    from collection_assistant.db.models import Customer
    try:
        with db_session() as session:
            count = session.query(Customer).count()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)[:80]}"
        count = 0
    return HealthResponse(status="healthy", database=db_status, customer_count=count)
