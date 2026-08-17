from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import kullanici_getir, verify_api_key
from modules.weather import service
from yetki import bakilan_sahip

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/")
async def get_weather(
    kisi: Optional[int] = Query(None, description="Kimin konumu (boşsa kendi)"),
    user: dict = Depends(verify_api_key),
):
    """Hava durumu, bakılan kişinin konumuna göre.

    Karşı tarafa geçtiğinde onun havasını görüyorsun — panelin geri kalanı
    gibi. Konumu hiç kaydedilmemişse env'deki varsayılan (Elazığ) kullanılır.
    """
    try:
        sahip = bakilan_sahip(user, kisi)
        return await service.get_weather(kullanici_getir(sahip))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Hava durumu alınamadı: {e}")
