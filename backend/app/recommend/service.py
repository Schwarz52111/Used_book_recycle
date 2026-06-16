"""推荐服务。

为用户推荐在库二手书：
  打分 = 书目热度 + 0.5 × 用户对该品类的偏好分
偏好来自用户的购买（强信号，+2/次）与回收（弱信号，+1/次）历史按品类累计。
无历史的新用户退化为按热度的“校园热门”冷启动。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts.service import get_or_create_user
from app.models import (
    Book,
    CourseTextbook,
    Inventory,
    InventoryStatus,
    LedgerEntry,
    LedgerType,
    Order,
    OrderStatus,
    RecycleRecord,
    User,
    UserProfile,
)

CAT_W_BUY = 2
CAT_W_SELL = 1


def _affinity(db: Session, user_id: int) -> dict[str, int]:
    aff: dict[str, int] = {}
    # 购买历史
    for (cat,) in db.execute(
        select(Book.category)
        .select_from(Order)
        .join(Inventory, Order.inventory_id == Inventory.id)
        .join(Book, Inventory.book_id == Book.id)
        .where(Order.buyer_id == user_id, Order.status == OrderStatus.completed)
    ).all():
        if cat:
            aff[cat] = aff.get(cat, 0) + CAT_W_BUY
    # 回收历史（通过回收到账流水回溯）
    for (cat,) in db.execute(
        select(Book.category)
        .select_from(LedgerEntry)
        .join(RecycleRecord, RecycleRecord.id == LedgerEntry.ref_id)
        .join(Book, RecycleRecord.book_id == Book.id)
        .where(
            LedgerEntry.user_id == user_id,
            LedgerEntry.ref_type == "recycle_record",
            LedgerEntry.entry_type == LedgerType.payout,
        )
    ).all():
        if cat:
            aff[cat] = aff.get(cat, 0) + CAT_W_SELL
    return aff


def get_profile(db: Session, openid: str) -> dict:
    user = db.scalar(select(User).where(User.openid == openid))
    if not user:
        return {"major": "", "semester": 0}
    p = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    return {"major": p.major if p else "", "semester": p.semester if p else 0}


def set_profile(db: Session, openid: str, major: str, semester: int) -> dict:
    user = get_or_create_user(db, openid)
    p = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if not p:
        p = UserProfile(user_id=user.id)
        db.add(p)
    p.major = (major or "").strip()
    p.semester = int(semester or 0)
    db.commit()
    return {"major": p.major, "semester": p.semester}


def textbook_recommend(db: Session, openid: str, limit: int = 8) -> list[dict]:
    """按用户专业+学期，推在库的本学期教材。"""
    prof = get_profile(db, openid)
    if not prof["major"] or not prof["semester"]:
        return []
    courses = list(
        db.scalars(
            select(CourseTextbook).where(
                CourseTextbook.major == prof["major"],
                CourseTextbook.semester == prof["semester"],
            )
        ).all()
    )
    out: list[dict] = []
    seen: set[int] = set()
    for ct in courses:
        item = db.scalar(
            select(Inventory)
            .join(Book, Inventory.book_id == Book.id)
            .where(Book.isbn == ct.isbn, Inventory.status == InventoryStatus.in_stock)
        )
        if not item or item.book_id in seen:
            continue
        seen.add(item.book_id)
        book = item.book
        out.append(
            {
                "id": item.id,
                "book_id": book.id,
                "title": book.title,
                "isbn": book.isbn,
                "condition_level": item.condition_level,
                "sale_price": float(item.sale_price or 0),
                "cover_url": book.cover_url or "",
                "machine_id": item.machine_id,
                "slot_code": item.slot_code,
                "status": item.status.value,
                "reason": f"本学期教材 · {ct.course_name}",
                "course": ct.course_name,
            }
        )
        if len(out) >= limit:
            break
    return out


def recommend(db: Session, openid: str = "", limit: int = 6) -> list[dict]:
    user = get_or_create_user(db, openid) if openid else None
    aff = _affinity(db, user.id) if user else {}

    rows = db.execute(
        select(Inventory, Book)
        .join(Book, Inventory.book_id == Book.id)
        .where(Inventory.status == InventoryStatus.in_stock)
    ).all()

    seen: set[int] = set()
    scored: list[tuple[float, Inventory, Book, str]] = []
    for inv, book in rows:
        if book.id in seen:
            continue
        seen.add(book.id)
        heat = float(book.heat_score or 0)
        boost = aff.get(book.category, 0)
        score = heat + 0.5 * boost
        if boost > 0:
            reason = f"你常看「{book.category}」"
        elif heat >= 0.5:
            reason = "校园热门"
        else:
            reason = "新近上架"
        scored.append((score, inv, book, reason))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, inv, book, reason in scored[:limit]:
        out.append(
            {
                "id": inv.id,
                "book_id": book.id,
                "title": book.title,
                "isbn": book.isbn,
                "condition_level": inv.condition_level,
                "sale_price": float(inv.sale_price or 0),
                "cover_url": book.cover_url or "",
                "machine_id": inv.machine_id,
                "slot_code": inv.slot_code,
                "status": inv.status.value,
                "reason": reason,
            }
        )
    return out
