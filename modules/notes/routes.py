from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from auth import verify_api_key
from database import get_db
from modules.notes import service
from yetki import bakilan_sahip, yazma_izni

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
def create_note(data: NoteCreate, user: dict = Depends(verify_api_key)):
    with get_db() as conn:
        return service.create_note(conn, user["id"], data.title, data.content, data.category)


@router.get("/search")
def search_notes(
    q: str = Query(..., description="Arama terimi"),
    category: Optional[str] = None,
    kisi: Optional[int] = Query(None, description="Kimin notlarında aransın (boşsa kendi)"),
    user: dict = Depends(verify_api_key),
):
    with get_db() as conn:
        return service.search_notes(conn, bakilan_sahip(user, kisi), q, category)


@router.get("/")
def list_notes(
    category: Optional[str] = None,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    kisi: Optional[int] = Query(None, description="Kimin notları (boşsa kendi)"),
    user: dict = Depends(verify_api_key),
):
    with get_db() as conn:
        return service.list_notes(
            conn, bakilan_sahip(user, kisi), category, limit=limit, offset=offset
        )


@router.get("/{note_id}")
def get_note(note_id: int, user: dict = Depends(verify_api_key)):
    """Okuma serbest — sahiplik kontrolü yok, ikiniz de birbirinizin notunu açabiliyorsunuz."""
    with get_db() as conn:
        result = service.get_note_by_id(conn, note_id)
    if not result:
        raise HTTPException(status_code=404, detail="Not bulunamadı")
    return result


@router.put("/{note_id}")
def update_note(note_id: int, data: NoteUpdate, user: dict = Depends(verify_api_key)):
    with get_db() as conn:
        yazma_izni(service.get_note_by_id(conn, note_id), user, "Not")
        return service.update_note(
            conn, user["id"], note_id, data.title, data.content, data.category
        )


@router.delete("/{note_id}")
def delete_note(note_id: int, user: dict = Depends(verify_api_key)):
    with get_db() as conn:
        yazma_izni(service.get_note_by_id(conn, note_id), user, "Not")
        service.delete_note(conn, user["id"], note_id)
    return {"message": "Not silindi"}
