from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.config import settings
from apps.api.db import init_db
from apps.api.routes.health import router as health_router
from apps.api.routes.leads import router as leads_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(leads_router)