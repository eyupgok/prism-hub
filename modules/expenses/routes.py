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


# ── Bütçe endpoint'leri ──────────────────────────────────────────────────────

budget_router = APIRouter(prefix="/api/budget", tags=["budget"])


class BudgetSet(BaseModel):
    category: str
    monthly_limit: float


@budget_router.get("/")
def list_budgets():
    """Tüm bütçe limitlerini, bu ayki harcama ve uyarı durumuyla döner"""
    with get_db() as conn:
        budgets = service.get_all_budgets(conn)
        summary = service.get_monthly_summary(conn)
        for b in budgets:
            b["current_spent"] = summary["by_category"].get(b["category"], 0)
            b["alert"] = service.check_budget_alert(conn, b["category"])
        return budgets


@budget_router.put("/")
def set_budget(data: BudgetSet):
    if data.category not in service.VALID_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Geçersiz kategori. Geçerli: {', '.join(sorted(service.VALID_CATEGORIES))}",
        )
    if data.monthly_limit <= 0:
        raise HTTPException(status_code=422, detail="Limit 0'dan büyük olmalı")
    with get_db() as conn:
        return service.set_budget(conn, data.category, data.monthly_limit)


@budget_router.delete("/{category}")
def delete_budget(category: str):
    with get_db() as conn:
        success = service.delete_budget(conn, category)
    if not success:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    return {"message": "Bütçe limiti kaldırıldı"}
