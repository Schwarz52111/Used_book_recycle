"""运营分析接口：热度重算与运营概览。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.heat import _sales_by_book, recompute_heat
from app.db import get_db
from app.models import (
    Book,
    Inventory,
    InventoryStatus,
    Order,
    OrderStatus,
    RecycleRecord,
    ReviewStatus,
    ReviewTask,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/heat/recompute")
def heat_recompute(db: Session = Depends(get_db)):
    """重算全部书目热度并写回，返回按热度降序的明细。"""
    rows = recompute_heat(db)
    return {
        "count": len(rows),
        "books": [
            {"book_id": r.book_id, "title": r.title, "heat": r.heat, "sales": r.sales, "recycles": r.recycles}
            for r in rows
        ],
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """运营概览：书目数、在库数、成交数与成交额、热度前 5。"""
    book_count = db.scalar(select(func.count(Book.id))) or 0
    in_stock = db.scalar(
        select(func.count(Inventory.id)).where(Inventory.status == InventoryStatus.in_stock)
    ) or 0
    sold = db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.completed)
    ) or 0
    revenue = db.scalar(
        select(func.coalesce(func.sum(Order.amount), 0)).where(Order.status == OrderStatus.completed)
    ) or 0

    top = db.execute(
        select(Book.id, Book.title, Book.heat_score).order_by(Book.heat_score.desc()).limit(5)
    ).all()

    return {
        "books": book_count,
        "in_stock": in_stock,
        "sold": sold,
        "revenue": round(float(revenue), 2),
        "top_heat": [{"book_id": bid, "title": t, "heat": float(h or 0)} for bid, t, h in top],
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """运营看板聚合数据：KPI + 热度排行 + 近期成交。"""
    in_stock = db.scalar(
        select(func.count(Inventory.id)).where(Inventory.status == InventoryStatus.in_stock)
    ) or 0
    sold = db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.completed)) or 0
    revenue = db.scalar(
        select(func.coalesce(func.sum(Order.amount), 0)).where(Order.status == OrderStatus.completed)
    ) or 0
    recycled = db.scalar(select(func.count(RecycleRecord.id))) or 0
    review_pending = db.scalar(
        select(func.count(ReviewTask.id)).where(ReviewTask.status == ReviewStatus.pending)
    ) or 0

    sales = _sales_by_book(db)
    top_rows = db.execute(
        select(Book.id, Book.title, Book.heat_score).order_by(Book.heat_score.desc()).limit(8)
    ).all()
    top_heat = [
        {"book_id": bid, "title": t, "heat": float(h or 0), "sales": sales.get(bid, 0)}
        for bid, t, h in top_rows
    ]

    recent_rows = db.execute(
        select(Order.order_no, Order.amount, Order.created_at, Book.title)
        .select_from(Order)
        .join(Inventory, Order.inventory_id == Inventory.id)
        .join(Book, Inventory.book_id == Book.id)
        .where(Order.status == OrderStatus.completed)
        .order_by(Order.id.desc())
        .limit(8)
    ).all()
    recent = [
        {
            "order_no": no,
            "amount": round(float(amt or 0), 2),
            "title": title,
            "time": created.isoformat() if created else "",
        }
        for no, amt, created, title in recent_rows
    ]

    from app.inventory.service import capacity_status

    return {
        "kpi": {
            "in_stock": in_stock,
            "sold": sold,
            "revenue": round(float(revenue), 2),
            "recycled": recycled,
            "review_pending": review_pending,
        },
        "capacity": capacity_status(db, "KIOSK-01"),
        "top_heat": top_heat,
        "recent": recent,
    }
