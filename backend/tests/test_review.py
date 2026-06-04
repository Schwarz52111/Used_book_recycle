"""人工复核测试（SQLite）。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.service import credit_recycle_payout, get_or_create_user
from app.db import Base
from app.models import (
    Book,
    Inventory,
    InventoryStatus,
    RecycleRecord,
    ReviewStatus,
    ReviewTask,
)
from app.review import service as review


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _setup(db, ai_price=10.0):
    book = Book(isbn="9787000000009", title="待复核书", author="", publisher="",
                category="", original_price=40, market_price=20, base_recycle_rate=0.35)
    db.add(book); db.commit(); db.refresh(book)
    rec = RecycleRecord(book_id=book.id, condition_level="good", evaluated_price=ai_price)
    db.add(rec); db.commit(); db.refresh(rec)
    item = Inventory(book_id=book.id, recycle_record_id=rec.id, condition_level="good",
                     cost_price=ai_price, sale_price=ai_price * 1.8, machine_id="KIOSK-01",
                     slot_code="A1", status=InventoryStatus.in_stock)
    db.add(item); db.commit(); db.refresh(item)
    seller = get_or_create_user(db, "openid_seller_x")
    credit_recycle_payout(db, seller, ai_price, rec.id)   # 卖家已到账 ai_price
    task = ReviewTask(recycle_record_id=rec.id, reason="seller_price_higher",
                      status=ReviewStatus.pending)
    db.add(task); db.commit(); db.refresh(task)
    return rec, item, seller, task


def test_correct_topups_seller():
    db = _session()
    rec, item, seller, task = _setup(db, ai_price=10.0)
    assert float(seller.balance) == 10.0
    review.resolve(db, task.id, "correct", new_price=15.0, operator="老师A")
    db.refresh(seller); db.refresh(item); db.refresh(task)
    assert float(item.cost_price) == 15.0
    assert float(seller.balance) == 15.0          # 补差 +5
    assert task.status == ReviewStatus.corrected


def test_reject_scraps_and_reverses():
    db = _session()
    rec, item, seller, task = _setup(db, ai_price=10.0)
    review.resolve(db, task.id, "reject", note="盗版", operator="老师B")
    db.refresh(seller); db.refresh(item); db.refresh(task)
    assert item.status == InventoryStatus.scrapped
    assert float(seller.balance) == 0.0           # 回收款冲正
    assert task.status == ReviewStatus.rejected


def test_approve_no_change():
    db = _session()
    rec, item, seller, task = _setup(db, ai_price=10.0)
    review.resolve(db, task.id, "approve", operator="老师C")
    db.refresh(seller); db.refresh(task)
    assert float(seller.balance) == 10.0
    assert task.status == ReviewStatus.approved


def test_cannot_resolve_twice():
    db = _session()
    rec, item, seller, task = _setup(db)
    review.resolve(db, task.id, "approve")
    try:
        review.resolve(db, task.id, "approve")
        assert False, "已处理任务不应可再处理"
    except review.ReviewError:
        pass


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name)
    print("ALL TESTS PASSED")
