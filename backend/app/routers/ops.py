"""运营处置接口：滞销清单与降价/捐赠/调拨。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.ops import service

router = APIRouter(prefix="/ops", tags=["ops"])


class MarkdownRequest(BaseModel):
    inventory_id: int
    new_price: float | None = None


class IdRequest(BaseModel):
    inventory_id: int


class TransferRequest(BaseModel):
    inventory_id: int
    to_machine: str


@router.get("/slow-movers")
def slow_movers(markdown_days: int = 14, donate_days: int = 30, db: Session = Depends(get_db)):
    return service.slow_movers(db, markdown_days, donate_days)


@router.post("/markdown")
def markdown(req: MarkdownRequest, db: Session = Depends(get_db)):
    try:
        item = service.markdown(db, req.inventory_id, req.new_price)
    except service.OpsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"inventory_id": item.id, "sale_price": float(item.sale_price)}


@router.post("/donate")
def donate(req: IdRequest, db: Session = Depends(get_db)):
    try:
        item = service.donate(db, req.inventory_id)
    except service.OpsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"inventory_id": item.id, "status": item.status.value}


@router.post("/transfer")
def transfer(req: TransferRequest, db: Session = Depends(get_db)):
    try:
        item = service.transfer(db, req.inventory_id, req.to_machine)
    except service.OpsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"inventory_id": item.id, "machine_id": item.machine_id, "slot_code": item.slot_code}
