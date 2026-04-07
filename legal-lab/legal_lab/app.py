from contextlib import asynccontextmanager

from fastapi import FastAPI

from legal_lab.config import settings
from legal_lab.db import init_db
from legal_lab.routes.health import router as health_router
from legal_lab.routes.cases import router as cases_router
from legal_lab.routes.source_links import router as source_links_router


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
app.include_router(cases_router)
app.include_router(source_links_router)
