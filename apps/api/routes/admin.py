"""Admin routes — boat and gallery management for operators."""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from apps.api.auth import require_api_key
from apps.api.services import admin as admin_svc


# Public router: serves the admin HTML shell (auth handled by frontend)
public_router = APIRouter()

# Protected router: all data operations require API key
router = APIRouter(
    prefix="/internal/admin",
    dependencies=[Depends(require_api_key)],
)

ADMIN_HTML_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "admin.html")
)


@public_router.get("/internal/admin/", response_class=HTMLResponse)
def admin_page():
    try:
        with open(ADMIN_HTML_PATH, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(500, "admin.html no encontrado")


# --- Boat list & detail ---


@router.get("/boats")
def list_boats():
    return admin_svc.list_boats()


@router.get("/boats/{slug}")
def get_boat(slug: str):
    boat = admin_svc.get_boat(slug)
    if not boat:
        raise HTTPException(404, "Barco no encontrado")
    return boat


# --- Boat data (text/specs editing) ---


@router.get("/boats/{slug}/data")
def get_boat_data(slug: str):
    data = admin_svc.get_boat_data(slug)
    if not data:
        raise HTTPException(404, "Barco no encontrado")
    return data


@router.put("/boats/{slug}/data")
def update_boat_data(slug: str, body: dict):
    ok, msg = admin_svc.update_boat_data(slug, body)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "ok", "message": msg}


class VisibilityRequest(BaseModel):
    visible: bool


@router.patch("/boats/{slug}/visibility")
def patch_visibility(slug: str, body: VisibilityRequest):
    ok, msg = admin_svc.set_boat_visibility(slug, body.visible)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "ok", "message": msg}


# --- Gallery ---


class GalleryUpdateRequest(BaseModel):
    files: list[str]


@router.put("/boats/{slug}/gallery")
def update_gallery(slug: str, body: GalleryUpdateRequest):
    ok, msg = admin_svc.update_gallery_order(slug, body.files)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "ok", "message": msg}


# --- Create ---


class BoatCreateRequest(BaseModel):
    slug: str
    name: str


@router.post("/boats")
def create_boat(body: BoatCreateRequest):
    ok, msg = admin_svc.create_boat(body.slug, body.name)
    if not ok:
        raise HTTPException(400, msg)
    return {"status": "ok", "message": msg}


# --- Build ---


@router.post("/build")
def build_site():
    ok, output = admin_svc.run_build()
    if not ok:
        raise HTTPException(500, output)
    return {"status": "ok", "output": output}


@router.post("/regenerate")
def regenerate():
    """Backwards-compatible alias for build."""
    ok, output = admin_svc.run_build()
    if not ok:
        raise HTTPException(500, output)
    return {"status": "ok", "output": output}


# --- Images ---


@router.get("/boats/{slug}/images/{filename}")
def get_image(slug: str, filename: str):
    path = admin_svc.get_image_path(slug, filename)
    if not path:
        raise HTTPException(404, "Imagen no encontrada")
    return FileResponse(path, media_type="image/jpeg")
