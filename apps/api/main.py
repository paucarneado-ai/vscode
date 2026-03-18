import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from apps.api.config import settings
from apps.api.db import init_db
from apps.api.routes.health import router as health_router
from apps.api.routes.internal import router as internal_router
from apps.api.routes.leads import router as leads_router

_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0,
        send_default_pii=False,
    )


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
app.include_router(internal_router)
app.include_router(leads_router)