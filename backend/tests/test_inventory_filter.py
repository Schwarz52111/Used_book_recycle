"""库存搜索/分类筛选测试（SQLite）。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.inventory.service import list_categories, list_inventory
from app.models import Book, Inventory, InventoryStatus


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _seed(db, isbn, title, author, cat):
    b = Book(isbn=isbn, title=title, author=author, publisher="", category=cat,
             original_price=40, market_price=20, base_recycle_rate=0.35)
    db.add(b); db.commit(); db.refresh(b)
    db.add(Inventory(book_id=b.id, condition_level="good", cost_price=8, sale_price=16,
                     machine_id="KIOSK-01", slot_code="A1", status=InventoryStatus.in_stock))
    db.commit()


def test_filter_by_category_and_query():
    db = _session()
    _seed(db, "9780000000c1", "算法导论", "Cormen", "计算机")
    _seed(db, "9780000000c2", "线性代数", "同济", "教材")

    assert set(list_categories(db)) == {"计算机", "教材"}

    comp = list_inventory(db, category="计算机")
    assert len(comp) == 1 and comp[0].book.title == "算法导论"

    by_title = list_inventory(db, q="线性")
    assert len(by_title) == 1 and by_title[0].book.title == "线性代数"

    by_author = list_inventory(db, q="Cormen")
    assert len(by_author) == 1

    assert list_inventory(db, q="不存在的书") == []


if __name__ == "__main__":
    test_filter_by_category_and_query()
    print("ALL TESTS PASSED")
