"""账户服务：用户的增改查与账本记账。

所有余额变动都必须经过 post_ledger，保证"余额 = 历史流水之和"，可对账可追溯。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, LedgerType, User


class AccountError(RuntimeError):
    pass


def get_or_create_user(db: Session, openid: str, nickname: str = "") -> User:
    user = db.scalar(select(User).where(User.openid == openid))
    if user:
        return user
    user = User(openid=openid, nickname=nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def post_ledger(
    db: Session,
    user: User,
    entry_type: LedgerType,
    amount: float,
    ref_type: str = "",
    ref_id: int | None = None,
    note: str = "",
) -> LedgerEntry:
    """记一笔账并同步更新余额。amount 正为入账、负为出账。"""
    new_balance = float(Decimal(str(user.balance or 0)) + Decimal(str(amount)))
    if new_balance < 0:
        raise AccountError("余额不足")
    user.balance = new_balance
    entry = LedgerEntry(
        user_id=user.id,
        entry_type=entry_type,
        amount=amount,
        balance_after=new_balance,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def credit_recycle_payout(db: Session, user: User, amount: float, recycle_record_id: int) -> LedgerEntry:
    """回收到账：卖书金额入卖家余额。"""
    return post_ledger(
        db, user, LedgerType.payout, abs(amount),
        ref_type="recycle_record", ref_id=recycle_record_id, note="回收到账",
    )


CREDIT_MIN, CREDIT_MAX = 0, 150


def adjust_credit(db: Session, user: User, delta: int) -> int:
    """调整用户信用分，封顶在 [0, 150]。返回新分值。"""
    new = int(user.credit_score or 100) + int(delta)
    user.credit_score = max(CREDIT_MIN, min(CREDIT_MAX, new))
    db.commit()
    return user.credit_score


def list_ledger(db: Session, user_id: int, limit: int = 50) -> list[LedgerEntry]:
    return list(
        db.scalars(
            select(LedgerEntry).where(LedgerEntry.user_id == user_id)
            .order_by(LedgerEntry.id.desc()).limit(limit)
        ).all()
    )
