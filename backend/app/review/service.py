"""复核服务：列任务、通过 / 修正回收价 / 驳回。

卖家身份通过"回收到账"那条账本流水回溯（ref_type=recycle_record, ref_id=record.id），
因此修正价与驳回冲正都能精确作用到原卖家账户。
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts.service import post_ledger
from app.models import (
    Book,
    Inventory,
    InventoryStatus,
    LedgerEntry,
    LedgerType,
    RecycleRecord,
    ReviewStatus,
    ReviewTask,
    User,
)


class ReviewError(RuntimeError):
    pass


def _seller_of(db: Session, record_id: int) -> User | None:
    entry = db.scalar(
        select(LedgerEntry).where(
            LedgerEntry.ref_type == "recycle_record",
            LedgerEntry.ref_id == record_id,
            LedgerEntry.entry_type == LedgerType.payout,
        )
    )
    return db.get(User, entry.user_id) if entry else None


def _item_of(db: Session, record_id: int) -> Inventory | None:
    return db.scalar(select(Inventory).where(Inventory.recycle_record_id == record_id))


def _safe_adjust(db: Session, user: User, amount: float, note: str) -> None:
    """给卖家余额加/减一笔；扣款不会把余额扣成负数（封顶到当前余额）。"""
    amount = round(float(amount), 2)
    bal = float(user.balance or 0)
    if amount < 0 and bal + amount < 0:
        amount = -bal
    if abs(amount) < 0.01:
        return
    ltype = LedgerType.topup if amount > 0 else LedgerType.purchase
    post_ledger(db, user, ltype, amount, ref_type="review", note=note)


def list_tasks(db: Session, status: str = "pending", limit: int = 100) -> list[dict]:
    stmt = select(ReviewTask).order_by(ReviewTask.id.desc()).limit(limit)
    if status:
        stmt = select(ReviewTask).where(ReviewTask.status == ReviewStatus(status)).order_by(
            ReviewTask.id.desc()
        ).limit(limit)
    rows = []
    for t in db.scalars(stmt).all():
        try:
            payload = json.loads(t.payload) if t.payload else {}
        except json.JSONDecodeError:
            payload = {}
        record = db.get(RecycleRecord, t.recycle_record_id) if t.recycle_record_id else None
        title = ""
        if record and record.book_id:
            book = db.get(Book, record.book_id)
            title = book.title if book else ""
        rows.append(
            {
                "id": t.id,
                "reason": t.reason,
                "status": t.status.value,
                "created_at": t.created_at.isoformat() if t.created_at else "",
                "record_id": t.recycle_record_id,
                "book_title": title,
                "condition_level": record.condition_level if record else "",
                "ai_price": float(record.evaluated_price) if record else None,
                "payload": payload,
                "operator": t.operator,
                "note": t.note,
            }
        )
    return rows


def resolve(
    db: Session,
    task_id: int,
    action: str,
    new_price: float | None = None,
    note: str = "",
    operator: str = "",
) -> ReviewTask:
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise ReviewError(f"复核任务不存在：{task_id}")
    if task.status != ReviewStatus.pending:
        raise ReviewError(f"该任务已处理：{task.status.value}")

    record = db.get(RecycleRecord, task.recycle_record_id) if task.recycle_record_id else None
    item = _item_of(db, record.id) if record else None
    seller = _seller_of(db, record.id) if record else None

    if action == "approve":
        task.status = ReviewStatus.approved

    elif action == "correct":
        if new_price is None:
            raise ReviewError("修正需提供新回收价")
        new_price = round(float(new_price), 2)
        old = float(item.cost_price) if item else (float(record.evaluated_price) if record else 0.0)
        delta = round(new_price - old, 2)
        if item:
            item.cost_price = new_price
        if record:
            record.evaluated_price = new_price
        if seller and abs(delta) >= 0.01:
            _safe_adjust(db, seller, delta, note=f"复核修正回收价（{old}→{new_price}）")
        task.status = ReviewStatus.corrected

    elif action == "reject":
        if item and item.status == InventoryStatus.in_stock:
            item.status = InventoryStatus.scrapped
        if seller and item:
            _safe_adjust(db, seller, -float(item.cost_price or 0), note="复核驳回·回收款冲正")
        task.status = ReviewStatus.rejected

    else:
        raise ReviewError(f"未知操作：{action}")

    task.operator = operator
    task.note = note
    task.resolved_at = datetime.now()
    db.commit()
    db.refresh(task)
    return task


def summary(db: Session) -> dict:
    from sqlalchemy import func

    rows = db.execute(
        select(ReviewTask.status, func.count(ReviewTask.id)).group_by(ReviewTask.status)
    ).all()
    return {status.value: n for status, n in rows}
