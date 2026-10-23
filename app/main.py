from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.routes.health import (
    router as health_router,
)
from app.api.routes.reviews import (
    router as reviews_router,
)
from app.api.routes.runs import (
    router as runs_router,
)
from app.api.routes.uploads import (
    router as uploads_router,
)
from app.core.config import settings
from app.core.database import (
    initialize_database,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(
        settings.upload_directory
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    Path(
        settings.output_directory
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    initialize_database()

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Deterministic-first parser-management "
        "workflow using LangGraph."
    ),
    lifespan=lifespan,
)


app.include_router(health_router)
app.include_router(uploads_router)
app.include_router(runs_router)
app.include_router(reviews_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": settings.app_name,
        "documentation": "/docs",
        "health": "/health",
        "readiness": "/health/ready",
        "upload": "/v1/uploads",
        "run_status": (
            "/v1/runs/{run_id}"
        ),
        "human_review": (
            "/v1/reviews/{run_id}"
        ),
    }
