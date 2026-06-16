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

# 信用等级：名称, 门槛下限, 颜色
CREDIT_TIERS = [
    ("青铜", 0, "#a9744f"),
    ("白银", 90, "#9aa3ad"),
    ("黄金", 110, "#c79a3a"),
    ("钻石", 130, "#3aa0c7"),
]
CREDIT_PERKS = {
    "青铜": ["基础回收价", "正常浏览与购买"],
    "白银": ["标准回收价", "复核优先处理"],
    "黄金": ["回收价上浮", "专属黄金标识"],
    "钻石": ["最高回收率", "新书优先回收额度"],
}


def credit_tier(credit_score: int | None) -> dict:
    """信用分 → 等级、权益、距下一级。"""
    score = int(credit_score if credit_score is not None else 100)
    name, low, color = CREDIT_TIERS[0]
    nxt = None
    for i, (n, l, c) in enumerate(CREDIT_TIERS):
        if score >= l:
            name, low, color = n, l, c
            nxt = CREDIT_TIERS[i + 1] if i + 1 < len(CREDIT_TIERS) else None
    return {
        "tier": name,
        "color": color,
        "tier_min": low,
        "perks": CREDIT_PERKS.get(name, []),
        "next_tier": nxt[0] if nxt else None,
        "next_at": nxt[1] if nxt else None,
    }


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
