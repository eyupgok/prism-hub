from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import get_db
from modules.reminders import service

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
def create_reminder(data: ReminderCreate):
    if data.recurrence not in VALID_RECURRENCES:
        raise HTTPException(status_code=422, detail=f"Geçersiz recurrence: {data.recurrence}")
    with get_db() as conn:
        return service.create_reminder(conn, data.title, data.due_datetime, data.priority, data.recurrence)


@router.get("/")
def list_reminders(include_completed: bool = False):
    with get_db() as conn:
        return service.list_reminders(conn, include_completed)


@router.get("/{reminder_id}")
def get_reminder(reminder_id: int):
    with get_db() as conn:
        result = service.get_reminder_by_id(conn, reminder_id)
    if not result:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")
    return result


@router.put("/{reminder_id}")
def update_reminder(reminder_id: int, data: ReminderUpdate):
    if data.recurrence is not None and data.recurrence not in VALID_RECURRENCES:
        raise HTTPException(status_code=422, detail=f"Geçersiz recurrence: {data.recurrence}")
    with get_db() as conn:
        if not service.get_reminder_by_id(conn, reminder_id):
            raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")
        return service.update_reminder(
            conn, reminder_id, data.title, data.due_datetime, data.priority, data.recurrence
        )


@router.put("/{reminder_id}/complete")
def complete_reminder(reminder_id: int):
    with get_db() as conn:
        result = service.complete_reminder(conn, reminder_id)
    if not result:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")
    return result


@router.put("/{reminder_id}/snooze/{minutes}")
def snooze_reminder(reminder_id: int, minutes: int):
    with get_db() as conn:
        result = service.snooze_reminder(conn, reminder_id, minutes)
    if not result:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")
    return result


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: int):
    with get_db() as conn:
        success = service.delete_reminder(conn, reminder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")
    return {"message": "Hatırlatıcı silindi"}
