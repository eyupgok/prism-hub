from fastapi import APIRouter, HTTPException

from modules.weather import service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/")
async def get_weather():
    try:
        return await service.get_weather()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Hava durumu alınamadı: {e}")
