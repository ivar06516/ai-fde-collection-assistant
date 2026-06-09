"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from collection_assistant.api.routes.collections import router as collections_router
from collection_assistant.api.routes.health import router as health_router
from collection_assistant.config import get_settings
from collection_assistant.db.session import create_all_tables
from collection_assistant.observability import setup_observability


class _RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind structured log context (workflow_id, customer_id) per HTTP request.

    Reads optional X-Workflow-Id / X-Customer-Id headers so that any log
    line emitted during the request automatically carries those IDs.
    Context is cleared after the response to prevent leaking into the next request.
    """
    async def dispatch(self, request: Request, call_next):
        from collection_assistant.observability.logging_config import (
            bind_workflow_context, clear_workflow_context,
        )
        workflow_id = request.headers.get("x-workflow-id", "")
        customer_id = request.headers.get("x-customer-id", "")
        if workflow_id:
            bind_workflow_context(workflow_id, customer_id)
        try:
            return await call_next(request)
        finally:
            if workflow_id:
                clear_workflow_context()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_observability(get_settings())
    create_all_tables()
    # FastAPI auto-instrumentation — creates spans for every HTTP request
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass
    yield


app = FastAPI(
    title="AI Collection Assistant API",
    description="Multi-agent collection pipeline - Forward Deployed Engineer PoC",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(_RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # m-2 fix: credentials=True + origins=* violates CORS spec
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(collections_router)


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("collection_assistant.api.main:app", host=settings.api_host,
                port=settings.api_port, reload=True)
