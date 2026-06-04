"""库存服务：回收入库、列库存、出货（含状态机流转）。"""

from __future__ import annotations

import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.inventory.dispense import DispenseResult, get_dispenser
from app.models import (
    Book,
    Inventory,
    InventoryStatus,
    RecycleRecord,
    ReviewStatus,
    ReviewTask,
)
from app.pricing.engine import evaluate_price

MIN_PRICE = 1.0


class InventoryError(RuntimeError):
    pass


def resolve_payout(ai_price: float, seller_price: float | None) -> tuple[float, bool]:
    """根据 AI 估价与卖家改价，得出最终回收价与是否需复核。

    - 未改价：用 AI 估价。
    - 改价 ≤ AI 估价：直接采用（卖家愿意收更少，放行）。
    - 改价 > AI 估价：先按 AI 估价到账，并标记人工复核（防止乱报高价），
      更高的报价由运营复核后再决定是否补差，不自动放款。
    """
    ai_price = round(float(ai_price or 0), 2)
    if seller_price is None:
        return ai_price, False
    sp = max(MIN_PRICE, float(seller_price))
    if sp <= ai_price:
        return round(sp, 2), False
    return ai_price, True


def intake(
    db: Session,
    record_id: int,
    machine_id: str,
    slot_code: str = "",
    rfid_tag: str = "",
    seller_price: float | None = None,
) -> Inventory:
    """把一条已估价的回收记录入库为库存条目。可由卖家改价。"""
    record = db.get(RecycleRecord, record_id)
    if record is None:
        raise InventoryError(f"回收记录不存在：{record_id}")
    if record.book_id is None:
        raise InventoryError("该记录未匹配到书目，无法入库")

    # 回收价：AI 估价 + 卖家可选改价
    ai_price = float(record.evaluated_price or 0)
    cost_price, needs_review = resolve_payout(ai_price, seller_price)

    # 上架售价：用定价引擎按书目+品相重新计算（保证有售价可展示/售卖）
    sale_price = 0.0
    book = db.get(Book, record.book_id)
    if book is not None:
        sale_price = evaluate_price(db, book, record.condition_level).sale_price

    item = Inventory(
        book_id=record.book_id,
        recycle_record_id=record.id,
        condition_level=record.condition_level,
        cost_price=cost_price,
        sale_price=sale_price,
        machine_id=machine_id,
        slot_code=slot_code,
        rfid_tag=rfid_tag,
        status=InventoryStatus.in_stock,
    )
    db.add(item)

    # 卖家报价高于 AI 估价 → 记一条人工复核
    if needs_review:
        db.add(
            ReviewTask(
                recycle_record_id=record.id,
                reason="seller_price_higher",
                payload=json.dumps(
                    {"ai_price": ai_price, "seller_price": seller_price, "accepted_price": cost_price},
                    ensure_ascii=False,
                ),
                status=ReviewStatus.pending,
            )
        )

    db.commit()
    db.refresh(item)
    return item


def list_inventory(
    db: Session,
    machine_id: str | None = None,
    status: str = "in_stock",
    q: str | None = None,
    category: str | None = None,
) -> list[Inventory]:
    stmt = select(Inventory).where(Inventory.status == InventoryStatus(status))
    if machine_id:
        stmt = stmt.where(Inventory.machine_id == machine_id)
    if q or category:
        stmt = stmt.join(Book, Inventory.book_id == Book.id)
        if category:
            stmt = stmt.where(Book.category == category)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(Book.title.like(like), Book.isbn.like(like), Book.author.like(like))
            )
    return list(db.scalars(stmt).all())


def list_categories(db: Session, machine_id: str | None = None) -> list[str]:
    stmt = (
        select(Book.category)
        .select_from(Inventory)
        .join(Book, Inventory.book_id == Book.id)
        .where(Inventory.status == InventoryStatus.in_stock)
        .distinct()
    )
    if machine_id:
        stmt = stmt.where(Inventory.machine_id == machine_id)
    return [c for (c,) in db.execute(stmt).all() if c]


def dispense(db: Session, inventory_id: int, machine_id: str, mechanism: str = "simulated") -> DispenseResult:
    """出货：校验在库 → 触发硬件 → 标记已售。"""
    item = db.get(Inventory, inventory_id)
    if item is None:
        raise InventoryError(f"库存不存在：{inventory_id}")
    if item.status != InventoryStatus.in_stock:
        raise InventoryError(f"库存状态不可出货：{item.status.value}")

    dispenser = get_dispenser(mechanism)
    result = dispenser.dispense(machine_id, item.slot_code, item.rfid_tag)
    if not result.ok:
        raise InventoryError(f"出货失败：{result.message}")

    # 电子门型号需用户取书后再确认；这里 Phase 0 直接确认
    if result.requires_user_action:
        dispenser.confirm_taken(machine_id, item.slot_code, item.rfid_tag)

    item.status = InventoryStatus.sold
    db.commit()
    return result
