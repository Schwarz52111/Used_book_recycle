"""书目热度计算。

热度信号（越大越热）：
  - 售出次数（completed 订单）权重高 —— 直接代表需求
  - 回收次数（recycle_records）权重低 —— 代表供给/流通活跃度
原始分归一化到 0~1 写回 Book.heat_score，定价引擎的热度系数随之生效，形成闭环。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Book, Inventory, Order, OrderStatus, RecycleRecord

W_SALE = 2.0
W_RECYCLE = 1.0


@dataclass
class HeatRow:
    book_id: int
    title: str
    heat: float
    sales: int
    recycles: int


def _sales_by_book(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(Inventory.book_id, func.count(Order.id))
        .join(Inventory, Order.inventory_id == Inventory.id)
        .where(Order.status == OrderStatus.completed)
        .group_by(Inventory.book_id)
    ).all()
    return {bid: n for bid, n in rows if bid is not None}


def _recycles_by_book(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(RecycleRecord.book_id, func.count(RecycleRecord.id))
        .where(RecycleRecord.book_id.is_not(None))
        .group_by(RecycleRecord.book_id)
    ).all()
    return {bid: n for bid, n in rows if bid is not None}


def recompute_heat(db: Session) -> list[HeatRow]:
    """重算所有书目热度并写回。返回按热度降序的明细。"""
    sales = _sales_by_book(db)
    recycles = _recycles_by_book(db)

    books = list(db.scalars(select(Book)).all())
    raw = {
        b.id: W_SALE * sales.get(b.id, 0) + W_RECYCLE * recycles.get(b.id, 0)
        for b in books
    }
    max_raw = max(raw.values(), default=0.0) or 1.0

    result: list[HeatRow] = []
    for b in books:
        heat = round(raw[b.id] / max_raw, 4)
        b.heat_score = heat
        result.append(
            HeatRow(book_id=b.id, title=b.title, heat=heat,
                    sales=sales.get(b.id, 0), recycles=recycles.get(b.id, 0))
        )
    db.commit()
    result.sort(key=lambda r: r.heat, reverse=True)
    return result
