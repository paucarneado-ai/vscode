from fastapi import APIRouter

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/")
async def demo_index():
    return {"status": "ok", "message": "Demo endpoint"}
