"""动态回收准入调控。

根据"某书在库量 vs 热度"决定是否继续回收：
  - 在库已达上限且热度低 → 暂停回收（不再收，避免越积越多的滞销书）
  - 在库较多但仍有热度 → 限流回收（继续收但价更保守，由定价的库存系数体现）
  - 其余 → 正常回收
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Book, Inventory, InventoryStatus

STOCK_CAP = 5          # 单书在库上限
LOW_HEAT = 0.3         # 低热度阈值


@dataclass
class Admission:
    accepted: bool          # 是否继续回收
    throttled: bool         # 是否限流（仍收但更保守）
    in_stock: int
    heat: float
    reason: str


def in_stock_count(db: Session, book_id: int) -> int:
    return (
        db.scalar(
            select(func.count(Inventory.id)).where(
                Inventory.book_id == book_id,
                Inventory.status == InventoryStatus.in_stock,
            )
        )
        or 0
    )


def check_admission(db: Session, book: Book) -> Admission:
    stock = in_stock_count(db, book.id)
    heat = float(book.heat_score or 0)

    if stock >= STOCK_CAP and heat < LOW_HEAT:
        return Admission(
            accepted=False, throttled=False, in_stock=stock, heat=heat,
            reason=f"该书在库已达 {stock} 本且近期需求低，暂停回收",
        )
    if stock >= STOCK_CAP:
        return Admission(
            accepted=True, throttled=True, in_stock=stock, heat=heat,
            reason=f"该书在库较多（{stock} 本），已下调回收价",
        )
    return Admission(
        accepted=True, throttled=False, in_stock=stock, heat=heat,
        reason="正常回收",
    )
