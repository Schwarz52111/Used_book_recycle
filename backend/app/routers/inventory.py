"""库存与出货接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.accounts.service import adjust_credit, credit_recycle_payout, get_or_create_user
from app.db import get_db
from app.inventory import service
from app.schemas import DispenseRequest, IntakeRequest, InventoryItem

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/intake", response_model=InventoryItem)
def intake_endpoint(req: IntakeRequest, db: Session = Depends(get_db)):
    """确认回收：把一条估价记录入库；填了卖家 openid 则把回收金额计入其账户。"""
    try:
        item = service.intake(
            db, req.record_id, req.machine_id, req.slot_code, req.rfid_tag,
            seller_price=req.seller_price,
        )
    except service.InventoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 回收到账：把回收价(=库存成本价)计入卖家余额，并加信用分（正常回收 +2）
    # 卖家身份：优先 openid（小程序），其次手机号（设备端无登录时用）。
    seller = None
    if req.seller_openid:
        seller = get_or_create_user(db, req.seller_openid)
    elif req.seller_phone:
        phone = "".join(c for c in req.seller_phone if c.isdigit())
        if phone:
            seller = get_or_create_user(db, "phone:" + phone)
            if not seller.phone:
                seller.phone = phone
                db.commit()
    if seller:
        credit_recycle_payout(db, seller, float(item.cost_price or 0), req.record_id)
        adjust_credit(db, seller, 2)

    return _to_item(item)


@router.get("", response_model=list[InventoryItem])
def list_endpoint(
    machine_id: str | None = None,
    status: str = "in_stock",
    q: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    return [_to_item(it) for it in service.list_inventory(db, machine_id, status, q, category)]


@router.get("/categories", response_model=list[str])
def categories_endpoint(machine_id: str | None = None, db: Session = Depends(get_db)):
    return service.list_categories(db, machine_id)


@router.get("/capacity")
def capacity_endpoint(machine_id: str = "KIOSK-01", db: Session = Depends(get_db)):
    """设备库容与满仓预警。"""
    return service.capacity_status(db, machine_id)


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
        category=(it.book.category if it.book else "") or "",
        condition_level=it.condition_level,
        cost_price=float(it.cost_price or 0),
        sale_price=float(it.sale_price or 0),
        cover_url=(it.book.cover_url if it.book else "") or "",
        machine_id=it.machine_id,
        slot_code=it.slot_code,
        status=it.status.value,
    )
