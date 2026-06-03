"""定价引擎与品相兜底逻辑的单元测试（用 SQLite，不依赖 MySQL/VLM）。

运行：cd backend && python -m pytest -q   （或 python tests/test_pricing.py）
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.grading.condition_agent import _level_from_scores
from app.models import Book, ConditionRule
from app.pricing.engine import _heat_coef, _stock_coef, evaluate_price


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _seed_book(db, market=100.0, rate=0.35, heat=0.0):
    book = Book(isbn="9780000000001", title="测试书", author="作者", publisher="出版社",
                category="测试", original_price=200, market_price=market,
                base_recycle_rate=rate, heat_score=heat)
    db.add(book)
    for lvl, f in [("like_new", 0.9), ("good", 0.7), ("acceptable", 0.5), ("damaged", 0.3)]:
        db.add(ConditionRule(condition_level=lvl, description=lvl, price_factor=f))
    db.commit()
    db.refresh(book)
    return book


def test_recycle_price_basic():
    db = _session()
    book = _seed_book(db, market=100.0, rate=0.35, heat=0.0)
    res = evaluate_price(db, book, "good")
    # 100 * 0.35 * 0.7 * 0.8(heat0) * 1.0(stock0) = 19.6
    assert abs(res.recycle_price - 19.6) < 0.01
    assert res.sale_price > res.recycle_price
    assert res.reason and "回收价" in res.reason
    assert res.factors["condition_factor"] == 0.7


def test_condition_monotonic():
    db = _session()
    book = _seed_book(db, market=100.0)
    prices = {lvl: evaluate_price(db, book, lvl).recycle_price
              for lvl in ["damaged", "acceptable", "good", "like_new"]}
    assert prices["damaged"] < prices["acceptable"] < prices["good"] < prices["like_new"]


def test_heat_and_stock_coef():
    assert _heat_coef(0.0) == 0.8
    assert _heat_coef(1.0) == 1.2
    assert _stock_coef(0) == 1.0
    assert _stock_coef(10) == 0.6  # 触底


def test_sale_price_above_cost():
    db = _session()
    book = _seed_book(db, market=10.0)
    res = evaluate_price(db, book, "damaged")
    assert res.sale_price >= res.recycle_price + 1.0


def test_grading_fallback_levels():
    assert _level_from_scores(0.9, 0.9, 0.9) == "damaged"   # overall 高
    assert _level_from_scores(0.2, 0.2, 0.3) == "damaged"   # completeness 低
    assert _level_from_scores(0.4, 0.55, 0.9) == "acceptable"
    assert _level_from_scores(0.3, 0.3, 0.9) == "good"
    assert _level_from_scores(0.1, 0.1, 1.0) == "like_new"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL TESTS PASSED")
