"""定价引擎。

回收价 = 市场参考价 × 基础回收率 × 品相系数 × 热度系数 × 库存系数
售价   = max(回收价 × 加价倍数, 市场参考价 × 品相售价比)
所有系数与中间值都写进 reason / factors，保证可解释、可复核。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Book, ConditionRule, Inventory, InventoryStatus
from app.schemas import PriceResult

# 品相 → 回收系数（无 condition_rules 配置时的兜底）
DEFAULT_CONDITION_FACTOR = {
    "like_new": 0.90,
    "good": 0.70,
    "acceptable": 0.50,
    "damaged": 0.30,
}
# 品相 → 售价占市场价比例
CONDITION_SALE_RATIO = {
    "like_new": 0.75,
    "good": 0.60,
    "acceptable": 0.45,
    "damaged": 0.30,
}
SALE_MARKUP = 1.8   # 售价相对回收成本的最低加价倍数
MIN_PRICE = 1.0


def _condition_factor(db: Session, level: str) -> float:
    rule = db.scalar(select(ConditionRule).where(ConditionRule.condition_level == level))
    if rule and rule.price_factor is not None:
        return float(rule.price_factor)
    return DEFAULT_CONDITION_FACTOR.get(level, 0.4)


def _heat_coef(heat_score: float) -> float:
    """热度 0~1 → 系数 0.8~1.2。"""
    return round(0.8 + 0.4 * max(0.0, min(1.0, heat_score)), 3)


def _stock_coef(stock_count: int) -> float:
    """同书在库越多，回收越保守（鼓励多样性，避免超储）。0.6~1.0。"""
    return round(max(0.6, 1.0 - 0.1 * max(0, stock_count)), 3)


def credit_coef(credit_score: int | None) -> float:
    """信用分 → 回收系数：100→1.0，150→1.10，0→0.80，区间封顶 [0.8, 1.15]。"""
    if credit_score is None:
        return 1.0
    f = 1.0 + (float(credit_score) - 100) / 500.0
    return round(max(0.8, min(1.15, f)), 3)


def evaluate_price(
    db: Session, book: Book, condition_level: str, seller_credit: int | None = None
) -> PriceResult:
    market = float(book.market_price or 0)
    base_rate = float(book.base_recycle_rate or 0.35)
    cond_factor = _condition_factor(db, condition_level)
    heat = float(book.heat_score or 0)
    heat_coef = _heat_coef(heat)

    stock_count = (
        db.scalar(
            select(func.count(Inventory.id)).where(
                Inventory.book_id == book.id,
                Inventory.status == InventoryStatus.in_stock,
            )
        )
        or 0
    )
    stock_coef = _stock_coef(stock_count)
    cred_coef = credit_coef(seller_credit)

    recycle = market * base_rate * cond_factor * heat_coef * stock_coef * cred_coef
    recycle = round(max(recycle, MIN_PRICE), 2)

    sale_ratio = CONDITION_SALE_RATIO.get(condition_level, 0.4)
    sale = max(recycle * SALE_MARKUP, market * sale_ratio)
    sale = round(max(sale, recycle + MIN_PRICE), 2)

    factors = {
        "market_price": round(market, 2),
        "base_recycle_rate": round(base_rate, 3),
        "condition_factor": round(cond_factor, 3),
        "heat_coef": heat_coef,
        "stock_coef": stock_coef,
        "stock_count": stock_count,
        "credit_coef": cred_coef,
    }
    credit_part = (
        f" × 信用系数 {cred_coef:.2f}（信用分 {seller_credit}）" if seller_credit is not None else ""
    )
    reason = (
        f"市场参考价 {market:.2f} × 基础回收率 {base_rate:.2f} × 品相系数 {cond_factor:.2f}"
        f"（{condition_level}）× 热度系数 {heat_coef:.2f} × 库存系数 {stock_coef:.2f}"
        f"（在库 {stock_count} 本）{credit_part} = 回收价 {recycle:.2f} 元；"
        f"按品相售价比 {sale_ratio:.2f} 与加价 {SALE_MARKUP:.1f}× 取高，得售价 {sale:.2f} 元。"
    )

    return PriceResult(recycle_price=recycle, sale_price=sale, reason=reason, factors=factors)
