from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from database import get_db
from modules.notes import service

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteCreate(BaseModel):
    title: str
    content: str
    category: str = "genel"


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


@router.post("/")
def create_note(data: NoteCreate):
    with get_db() as conn:
        return service.create_note(conn, data.title, data.content, data.category)


@router.get("/search")
def search_notes(
    q: str = Query(..., description="Arama terimi"),
    category: Optional[str] = None,
):
    with get_db() as conn:
        return service.search_notes(conn, q, category)


@router.get("/")
def list_notes(category: Optional[str] = None):
    with get_db() as conn:
        return service.list_notes(conn, category)


@router.get("/{note_id}")
def get_note(note_id: int):
    with get_db() as conn:
        result = service.get_note_by_id(conn, note_id)
    if not result:
        raise HTTPException(status_code=404, detail="Not bulunamadı")
    return result


@router.put("/{note_id}")
def update_note(note_id: int, data: NoteUpdate):
    with get_db() as conn:
        if not service.get_note_by_id(conn, note_id):
            raise HTTPException(status_code=404, detail="Not bulunamadı")
        return service.update_note(conn, note_id, data.title, data.content, data.category)


@router.delete("/{note_id}")
def delete_note(note_id: int):
    with get_db() as conn:
        success = service.delete_note(conn, note_id)
    if not success:
        raise HTTPException(status_code=404, detail="Not bulunamadı")
    return {"message": "Not silindi"}
