from fastapi import FastAPI

from apps.api.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }