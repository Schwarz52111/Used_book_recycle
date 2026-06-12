"""滞销识别与处置。

滞销判定：在库时长 × 热度。在库越久、越冷门越该处理。
  - 在库 ≥ donate_days 且热度低 → 建议捐赠
  - 在库 ≥ markdown_days → 建议降价
运营可执行：降价 / 捐赠 / 跨机调拨。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inventory.service import allocate_slot, capacity_status
from app.models import Book, Inventory, InventoryStatus

LOW_HEAT = 0.2
MARKDOWN_PCT = 0.8


class OpsError(RuntimeError):
    pass


def slow_movers(db: Session, markdown_days: int = 14, donate_days: int = 30) -> list[dict]:
    now = datetime.now()
    rows = db.execute(
        select(Inventory, Book)
        .join(Book, Inventory.book_id == Book.id)
        .where(Inventory.status == InventoryStatus.in_stock)
    ).all()
    out = []
    for it, book in rows:
        age = (now - it.created_at).days if it.created_at else 0
        heat = float(book.heat_score or 0)
        if age >= donate_days and heat < LOW_HEAT:
            suggestion, sp = "建议捐赠", None
        elif age >= markdown_days:
            suggestion = f"建议降价至 {int(MARKDOWN_PCT * 100)}%"
            sp = round(float(it.sale_price or 0) * MARKDOWN_PCT, 2)
        else:
            continue
        out.append(
            {
                "inventory_id": it.id,
                "title": book.title,
                "days_in_stock": age,
                "heat": round(heat, 4),
                "sale_price": float(it.sale_price or 0),
                "machine_id": it.machine_id,
                "suggestion": suggestion,
                "suggested_price": sp,
            }
        )
    out.sort(key=lambda r: r["days_in_stock"], reverse=True)
    return out


def _get_in_stock(db: Session, inventory_id: int) -> Inventory:
    item = db.get(Inventory, inventory_id)
    if item is None:
        raise OpsError(f"库存不存在：{inventory_id}")
    if item.status != InventoryStatus.in_stock:
        raise OpsError(f"该库存状态不可处置：{item.status.value}")
    return item


def markdown(db: Session, inventory_id: int, new_price: float | None = None) -> Inventory:
    item = _get_in_stock(db, inventory_id)
    price = new_price if new_price is not None else float(item.sale_price or 0) * MARKDOWN_PCT
    item.sale_price = round(max(1.0, float(price)), 2)
    db.commit()
    db.refresh(item)
    return item


def donate(db: Session, inventory_id: int) -> Inventory:
    item = _get_in_stock(db, inventory_id)
    item.status = InventoryStatus.donated
    db.commit()
    db.refresh(item)
    return item


def transfer(db: Session, inventory_id: int, to_machine: str) -> Inventory:
    item = _get_in_stock(db, inventory_id)
    if not to_machine or to_machine == item.machine_id:
        raise OpsError("请指定不同的目标设备")
    if capacity_status(db, to_machine)["full"]:
        raise OpsError(f"目标设备 {to_machine} 已满仓")
    item.machine_id = to_machine
    item.slot_code = allocate_slot(db, to_machine) or ""
    db.commit()
    db.refresh(item)
    return item
