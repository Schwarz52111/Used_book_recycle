"""库存与出货接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.inventory import service
from app.schemas import DispenseRequest, IntakeRequest, InventoryItem

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/intake", response_model=InventoryItem)
def intake_endpoint(req: IntakeRequest, db: Session = Depends(get_db)):
    """确认回收：把一条估价记录入库。"""
    try:
        item = service.intake(db, req.record_id, req.machine_id, req.slot_code, req.rfid_tag)
    except service.InventoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_item(item)


@router.get("", response_model=list[InventoryItem])
def list_endpoint(machine_id: str | None = None, status: str = "in_stock", db: Session = Depends(get_db)):
    return [_to_item(it) for it in service.list_inventory(db, machine_id, status)]


@router.post("/dispense")
def dispense_endpoint(req: DispenseRequest, mechanism: str = "simulated", db: Session = Depends(get_db)):
    """购买后出货。mechanism: vend_channel | rfid_door | simulated。"""
    try:
        result = service.dispense(db, req.inventory_id, req.machine_id, mechanism)
    except service.InventoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


def _to_item(it) -> InventoryItem:
    return InventoryItem(
        id=it.id,
        book_id=it.book_id,
        title=it.book.title if it.book else "",
        isbn=it.book.isbn if it.book else "",
        condition_level=it.condition_level,
        sale_price=float(it.sale_price or 0),
        machine_id=it.machine_id,
        slot_code=it.slot_code,
        status=it.status.value,
    )
