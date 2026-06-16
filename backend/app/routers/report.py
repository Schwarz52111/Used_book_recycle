"""运营报表导出（CSV，UTF-8 BOM，Excel 直接打开不乱码）。"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Book,
    Inventory,
    InventoryStatus,
    Order,
    OrderStatus,
    RecycleRecord,
)

router = APIRouter(prefix="/report", tags=["report"])


def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    buf = io.StringIO()
    buf.write("﻿")  # BOM，确保 Excel 以 UTF-8 解析中文
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/recycle.csv")
def export_recycle(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            RecycleRecord.created_at, Book.title, RecycleRecord.condition_level,
            RecycleRecord.evaluated_price, RecycleRecord.recognize_confidence,
            RecycleRecord.condition_confidence,
        )
        .select_from(RecycleRecord)
        .join(Book, RecycleRecord.book_id == Book.id, isouter=True)
        .order_by(RecycleRecord.id.desc())
    ).all()
    data = [
        [
            t.isoformat() if t else "", title or "", cond or "",
            f"{float(price or 0):.2f}", f"{float(rc or 0):.2f}", f"{float(cc or 0):.2f}",
        ]
        for t, title, cond, price, rc, cc in rows
    ]
    return _csv_response(
        "recycle_records.csv",
        ["时间", "书名", "品相", "估价", "识别置信度", "品相置信度"],
        data,
    )


@router.get("/orders.csv")
def export_orders(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Order.order_no, Order.created_at, Book.title, Order.amount,
               Order.status, Order.pay_provider)
        .select_from(Order)
        .join(Inventory, Order.inventory_id == Inventory.id)
        .join(Book, Inventory.book_id == Book.id)
        .where(Order.status == OrderStatus.completed)
        .order_by(Order.id.desc())
    ).all()
    data = [
        [no, t.isoformat() if t else "", title or "", f"{float(amt or 0):.2f}",
         status.value, prov or ""]
        for no, t, title, amt, status, prov in rows
    ]
    return _csv_response(
        "orders.csv",
        ["订单号", "时间", "书名", "金额", "状态", "支付方式"],
        data,
    )


@router.get("/inventory.csv")
def export_inventory(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Inventory.id, Book.title, Book.isbn, Book.category,
               Inventory.condition_level, Inventory.cost_price, Inventory.sale_price,
               Inventory.machine_id, Inventory.slot_code)
        .select_from(Inventory)
        .join(Book, Inventory.book_id == Book.id)
        .where(Inventory.status == InventoryStatus.in_stock)
        .order_by(Inventory.id.desc())
    ).all()
    data = [
        [iid, title or "", isbn or "", cat or "", cond or "",
         f"{float(cost or 0):.2f}", f"{float(sale or 0):.2f}", mid or "", slot or ""]
        for iid, title, isbn, cat, cond, cost, sale, mid, slot in rows
    ]
    return _csv_response(
        "inventory.csv",
        ["库存ID", "书名", "ISBN", "分类", "品相", "成本价", "售价", "设备", "货道"],
        data,
    )
