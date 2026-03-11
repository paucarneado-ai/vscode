from fastapi import FastAPI

from apps.api.config import settings
from apps.api.routes.health import router as health_router


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.include_router(health_router)