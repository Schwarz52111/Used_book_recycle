"""个性化推荐测试（SQLite）。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.service import get_or_create_user
from app.db import Base
from app.models import Book, Inventory, InventoryStatus, Order, OrderStatus
from app.recommend.service import recommend


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _book(db, isbn, title, cat, heat):
    b = Book(isbn=isbn, title=title, author="", publisher="", category=cat,
             original_price=40, market_price=20, base_recycle_rate=0.35, heat_score=heat)
    db.add(b); db.commit(); db.refresh(b)
    return b


def _stock(db, book, status=InventoryStatus.in_stock):
    it = Inventory(book_id=book.id, condition_level="good", cost_price=8, sale_price=16,
                   machine_id="KIOSK-01", slot_code="A1", status=status)
    db.add(it); db.commit(); db.refresh(it)
    return it


def test_cold_start_by_heat():
    db = _session()
    a = _book(db, "9780000000a1", "计算机书", "计算机", 0.2)
    b = _book(db, "9780000000b1", "热门教材", "教材", 0.8)
    _stock(db, a); _stock(db, b)
    recos = recommend(db, openid="", limit=6)
    assert recos[0]["book_id"] == b.id          # 无历史 → 热度优先
    assert recos[0]["reason"] == "校园热门"


def test_personalized_by_purchase():
    db = _session()
    a = _book(db, "9780000000a2", "计算机书", "计算机", 0.2)
    b = _book(db, "9780000000b2", "热门教材", "教材", 0.8)
    _stock(db, a); _stock(db, b)                # 在库候选
    user = get_or_create_user(db, "openid_buyer")
    # 用户买过一本"计算机"类
    sold = _stock(db, a, status=InventoryStatus.sold)
    db.add(Order(order_no="O-1", inventory_id=sold.id, buyer_id=user.id, amount=16,
                 status=OrderStatus.completed))
    db.commit()
    recos = recommend(db, "openid_buyer", limit=6)
    assert recos[0]["book_id"] == a.id          # 偏好提升 → 计算机类反超热门
    assert "计算机" in recos[0]["reason"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name)
    print("ALL TESTS PASSED")
