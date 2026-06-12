"""滞销处置测试（SQLite）。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Book, Inventory, InventoryStatus
from app.ops.service import donate, markdown, slow_movers


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _book(db, isbn, title, heat=0.0):
    b = Book(isbn=isbn, title=title, author="", publisher="", category="测试",
             original_price=40, market_price=20, base_recycle_rate=0.35, heat_score=heat)
    db.add(b); db.commit(); db.refresh(b)
    return b


def _stock(db, book, days_old, sale=20.0):
    it = Inventory(book_id=book.id, condition_level="good", cost_price=6, sale_price=sale,
                   machine_id="KIOSK-01", slot_code="A1", status=InventoryStatus.in_stock,
                   created_at=datetime.now() - timedelta(days=days_old))
    db.add(it); db.commit(); db.refresh(it)
    return it


def test_slow_movers_and_actions():
    db = _session()
    fresh = _book(db, "9780000000s1", "新书"); _stock(db, fresh, 1)            # 不滞销
    stale = _book(db, "9780000000s2", "降价书", heat=0.0); s_it = _stock(db, stale, 20)   # 建议降价
    cold = _book(db, "9780000000s3", "捐赠书", heat=0.0); c_it = _stock(db, cold, 40)     # 建议捐赠

    rows = slow_movers(db)
    titles = {r["title"]: r for r in rows}
    assert "新书" not in titles                                   # 太新，不入列
    assert "建议降价" in titles["降价书"]["suggestion"]
    assert titles["降价书"]["suggested_price"] == 16.0            # 20×0.8
    assert titles["捐赠书"]["suggestion"] == "建议捐赠"

    markdown(db, s_it.id)                                          # 执行降价
    db.refresh(s_it); assert float(s_it.sale_price) == 16.0
    donate(db, c_it.id)                                            # 执行捐赠
    db.refresh(c_it); assert c_it.status == InventoryStatus.donated


if __name__ == "__main__":
    test_slow_movers_and_actions()
    print("ALL TESTS PASSED")
