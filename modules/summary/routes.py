from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import verify_api_key
from modules.summary import service
from yetki import bakilan_sahip

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("/")
async def get_summary(
    kisi: Optional[int] = Query(None, description="Kimin özeti (boşsa kendi)"),
    user: dict = Depends(verify_api_key),
):
    try:
        text = await service.get_morning_summary(bakilan_sahip(user, kisi))
        return {"summary": text}
    except HTTPException:
        raise            # bakilan_sahip'in 404'ü aşağıdaki 500'e yutulmasın
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Özet oluşturulamadı: {e}")
