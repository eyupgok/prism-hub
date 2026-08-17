from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from auth import verify_api_key
from database import get_db
from modules.reminders import service
from yetki import bakilan_sahip, yazma_izni

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


VALID_RECURRENCES = {"none", "daily", "weekly", "monthly"}


class ReminderCreate(BaseModel):
    title: str
    due_datetime: str
    priority: int = 3
    recurrence: str = "none"


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    due_datetime: Optional[str] = None
    priority: Optional[int] = None
    recurrence: Optional[str] = None


@router.post("/")
def create_reminder(data: ReminderCreate, user: dict = Depends(verify_api_key)):
    if data.recurrence not in VALID_RECURRENCES:
        raise HTTPException(status_code=422, detail=f"Geçersiz recurrence: {data.recurrence}")
    with get_db() as conn:
        return service.create_reminder(
            conn, user["id"], data.title, data.due_datetime, data.priority, data.recurrence
        )


@router.get("/")
def list_reminders(
    include_completed: bool = False,
    kisi: Optional[int] = Query(None, description="Kimin hatırlatıcıları (boşsa kendi)"),
    user: dict = Depends(verify_api_key),
):
    with get_db() as conn:
        return service.list_reminders(conn, bakilan_sahip(user, kisi), include_completed)


@router.get("/{reminder_id}")
def get_reminder(reminder_id: int, user: dict = Depends(verify_api_key)):
    """Okuma serbest — ikiniz de birbirinizin hatırlatıcısını açabiliyorsunuz."""
    with get_db() as conn:
        result = service.get_reminder_by_id(conn, reminder_id)
    if not result:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")
    return result


@router.put("/{reminder_id}")
def update_reminder(
    reminder_id: int, data: ReminderUpdate, user: dict = Depends(verify_api_key)
):
    if data.recurrence is not None and data.recurrence not in VALID_RECURRENCES:
        raise HTTPException(status_code=422, detail=f"Geçersiz recurrence: {data.recurrence}")
    with get_db() as conn:
        yazma_izni(service.get_reminder_by_id(conn, reminder_id), user, "Hatırlatıcı")
        return service.update_reminder(
            conn, user["id"], reminder_id,
            data.title, data.due_datetime, data.priority, data.recurrence,
        )


@router.put("/{reminder_id}/complete")
def complete_reminder(reminder_id: int, user: dict = Depends(verify_api_key)):
    with get_db() as conn:
        yazma_izni(service.get_reminder_by_id(conn, reminder_id), user, "Hatırlatıcı")
        return service.complete_reminder(conn, user["id"], reminder_id)


@router.put("/{reminder_id}/snooze/{minutes}")
def snooze_reminder(reminder_id: int, minutes: int, user: dict = Depends(verify_api_key)):
    with get_db() as conn:
        yazma_izni(service.get_reminder_by_id(conn, reminder_id), user, "Hatırlatıcı")
        return service.snooze_reminder(conn, user["id"], reminder_id, minutes)


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int, user: dict = Depends(verify_api_key)):
    with get_db() as conn:
        yazma_izni(service.get_reminder_by_id(conn, reminder_id), user, "Hatırlatıcı")
        service.delete_reminder(conn, user["id"], reminder_id)
    return {"message": "Hatırlatıcı silindi"}
