"""库容与货位分配测试（SQLite）。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base
from app.inventory.service import allocate_slot, capacity_status
from app.models import Book, Inventory, InventoryStatus


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _book(db):
    b = Book(isbn="9787000000600", title="库容书", author="", publisher="", category="测试",
             original_price=40, market_price=20, base_recycle_rate=0.35)
    db.add(b); db.commit(); db.refresh(b)
    return b


def _stock(db, book, slot):
    db.add(Inventory(book_id=book.id, condition_level="good", cost_price=8, sale_price=16,
                     machine_id="KIOSK-01", slot_code=slot, status=InventoryStatus.in_stock))
    db.commit()


def test_capacity_and_allocation():
    db = _session()
    s = get_settings()
    orig = s.machine_capacity
    s.machine_capacity = 3
    try:
        b = _book(db)
        _stock(db, b, "A1")
        _stock(db, b, "A2")
        assert allocate_slot(db, "KIOSK-01") == "A3"        # 跳过已占用，给下一个空位
        st = capacity_status(db, "KIOSK-01")
        assert st["used"] == 2 and st["free"] == 1 and not st["full"]

        _stock(db, b, "A3")
        st2 = capacity_status(db, "KIOSK-01")
        assert st2["full"] and st2["used"] == 3              # 满仓
        assert allocate_slot(db, "KIOSK-01") is None
    finally:
        s.machine_capacity = orig


if __name__ == "__main__":
    test_capacity_and_allocation()
    print("ALL TESTS PASSED")
