"""库存服务：回收入库、列库存、出货（含状态机流转）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inventory.dispense import DispenseResult, get_dispenser
from app.models import Book, Inventory, InventoryStatus, RecycleRecord
from app.pricing.engine import evaluate_price


class InventoryError(RuntimeError):
    pass


def intake(
    db: Session, record_id: int, machine_id: str, slot_code: str = "", rfid_tag: str = ""
) -> Inventory:
    """把一条已估价的回收记录入库为库存条目。"""
    record = db.get(RecycleRecord, record_id)
    if record is None:
        raise InventoryError(f"回收记录不存在：{record_id}")
    if record.book_id is None:
        raise InventoryError("该记录未匹配到书目，无法入库")

    # 上架售价：用定价引擎按书目+品相重新计算（保证有售价可展示/售卖）
    sale_price = 0.0
    book = db.get(Book, record.book_id)
    if book is not None:
        sale_price = evaluate_price(db, book, record.condition_level).sale_price

    item = Inventory(
        book_id=record.book_id,
        recycle_record_id=record.id,
        condition_level=record.condition_level,
        cost_price=record.evaluated_price,
        sale_price=sale_price,
        machine_id=machine_id,
        slot_code=slot_code,
        rfid_tag=rfid_tag,
        status=InventoryStatus.in_stock,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_inventory(db: Session, machine_id: str | None = None, status: str = "in_stock") -> list[Inventory]:
    stmt = select(Inventory).where(Inventory.status == InventoryStatus(status))
    if machine_id:
        stmt = stmt.where(Inventory.machine_id == machine_id)
    return list(db.scalars(stmt).all())


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
