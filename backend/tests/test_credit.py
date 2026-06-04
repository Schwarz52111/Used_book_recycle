"""信用分与差异化回收率测试（SQLite）。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.service import adjust_credit, get_or_create_user
from app.db import Base
from app.models import Book
from app.pricing.engine import credit_coef, evaluate_price


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _book(db):
    b = Book(isbn="9787000000777", title="信用书", author="", publisher="", category="测试",
             original_price=100, market_price=100, base_recycle_rate=0.35, heat_score=0)
    db.add(b); db.commit(); db.refresh(b)
    return b


def test_credit_coef_mapping():
    assert credit_coef(None) == 1.0
    assert credit_coef(100) == 1.0
    assert credit_coef(150) == 1.1
    assert credit_coef(0) == 0.8
    assert credit_coef(300) == 1.15     # 封顶
    assert credit_coef(-100) == 0.8     # 触底


def test_adjust_credit_clamps():
    db = _session()
    u = get_or_create_user(db, "openid_credit")
    assert u.credit_score == 100
    assert adjust_credit(db, u, 100) == 150     # 封顶 150
    assert adjust_credit(db, u, -1000) == 0     # 触底 0


def test_high_credit_pays_more():
    db = _session()
    b = _book(db)
    low = evaluate_price(db, b, "good", seller_credit=50).recycle_price
    base = evaluate_price(db, b, "good", seller_credit=100).recycle_price
    high = evaluate_price(db, b, "good", seller_credit=150).recycle_price
    assert low < base < high                    # 信用越高回收价越高


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name)
    print("ALL TESTS PASSED")
