"""热度分析与回收准入测试（SQLite，不依赖外部服务）。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analytics.admission import check_admission
from app.analytics.heat import recompute_heat
from app.db import Base
from app.models import Book, Inventory, InventoryStatus, Order, OrderStatus


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _book(db, isbn, title):
    b = Book(isbn=isbn, title=title, author="", publisher="", category="",
             original_price=50, market_price=30, base_recycle_rate=0.35)
    db.add(b); db.commit(); db.refresh(b)
    return b


def _add_inventory(db, book, status=InventoryStatus.in_stock):
    it = Inventory(book_id=book.id, condition_level="good", cost_price=10, sale_price=20,
                   machine_id="KIOSK-01", slot_code="A1", status=status)
    db.add(it); db.commit(); db.refresh(it)
    return it


def _complete_sale(db, book, n):
    for i in range(n):
        it = _add_inventory(db, book, status=InventoryStatus.sold)
        db.add(Order(order_no=f"O{book.id}-{i}", inventory_id=it.id, amount=20,
                     status=OrderStatus.completed))
    db.commit()


def test_heat_ordering():
    db = _session()
    a = _book(db, "9780000000001", "热门书")
    b = _book(db, "9780000000002", "冷门书")
    _complete_sale(db, a, 3)
    _complete_sale(db, b, 1)

    rows = recompute_heat(db)
    heat = {r.book_id: r.heat for r in rows}
    assert heat[a.id] == 1.0                 # 最热归一化到 1
    assert heat[a.id] > heat[b.id]
    db.refresh(a)
    assert float(a.heat_score) == 1.0        # 已写回 Book


def test_admission_blocks_overstock_lowheat():
    db = _session()
    book = _book(db, "9780000000003", "滞销书")  # heat 默认 0
    for _ in range(5):
        _add_inventory(db, book)                  # 5 本在库
    adm = check_admission(db, book)
    assert adm.accepted is False                  # 超储 + 低热 → 暂停回收
    assert adm.in_stock == 5


def test_admission_normal_when_low_stock():
    db = _session()
    book = _book(db, "9780000000004", "普通书")
    _add_inventory(db, book)
    _add_inventory(db, book)                       # 2 本在库
    adm = check_admission(db, book)
    assert adm.accepted is True
    assert adm.throttled is False


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name)
    print("ALL TESTS PASSED")
