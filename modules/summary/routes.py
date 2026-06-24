from fastapi import APIRouter, HTTPException

from modules.summary import service

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("/")
async def get_summary():
    try:
        text = await service.get_morning_summary()
        return {"summary": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Özet oluşturulamadı: {e}")
