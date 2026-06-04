"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from collection_assistant.api.routes.collections import router as collections_router
from collection_assistant.api.routes.health import router as health_router
from collection_assistant.db.session import create_all_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all_tables()
    yield


app = FastAPI(
    title="AI FDE Collection Assistant API",
    description="Multi-agent collection pipeline - Forward Deployed Engineer PoC",
    version="0.1.0",
    lifespan=lifespan,
)

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
    from collection_assistant.config import get_settings
    settings = get_settings()
    uvicorn.run("collection_assistant.api.main:app", host=settings.api_host,
                port=settings.api_port, reload=True)
