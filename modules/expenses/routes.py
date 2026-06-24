from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import get_db
from modules.expenses import service

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


class ExpenseCreate(BaseModel):
    amount: float
    category: str = "diğer"
    description: str = ""
    expense_date: Optional[str] = None


@router.post("/")
def create_expense(data: ExpenseCreate):
    with get_db() as conn:
        return service.create_expense(conn, data.amount, data.category, data.description, data.expense_date)


@router.get("/summary")
def get_summary(month: Optional[str] = None):
    with get_db() as conn:
        return service.get_monthly_summary(conn, month)


@router.get("/")
def list_expenses(month: Optional[str] = None, category: Optional[str] = None):
    with get_db() as conn:
        return service.list_expenses(conn, month, category)


@router.delete("/{expense_id}")
def delete_expense(expense_id: int):
    with get_db() as conn:
        success = service.delete_expense(conn, expense_id)
    if not success:
        raise HTTPException(status_code=404, detail="Harcama bulunamadı")
    return {"message": "Harcama silindi"}
