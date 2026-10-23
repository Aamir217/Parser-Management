from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/ready")
def readiness_check() -> dict:
    database_status = False

    try:
        with SessionLocal() as database:
            database.execute(text("SELECT 1"))
            database_status = True
    except Exception:
        database_status = False

    overall_status = (
        "ready"
        if database_status
        else "not_ready"
    )

    return {
        "status": overall_status,
        "checks": {
            "api": True,
            "database": database_status,
        },
    }
