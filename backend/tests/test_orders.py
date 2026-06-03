"""订单 + 回收到账流程测试（SQLite + 模拟支付，不依赖 MySQL/微信/VLM）。

运行：cd backend && python -m pytest -q
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.accounts.service import credit_recycle_payout, get_or_create_user, post_ledger
from app.db import Base
from app.models import (
    Book,
    Inventory,
    InventoryStatus,
    LedgerEntry,
    LedgerType,
    OrderStatus,
    RecycleRecord,
)
from app.orders import service as orders


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _seed_inventory(db, sale_price=30.0, cost_price=12.0):
    book = Book(isbn="9787000000001", title="测试书", author="作者", publisher="社",
                category="测试", original_price=60, market_price=40, base_recycle_rate=0.35)
    db.add(book); db.commit(); db.refresh(book)
    item = Inventory(book_id=book.id, condition_level="good", cost_price=cost_price,
                     sale_price=sale_price, machine_id="KIOSK-01", slot_code="A1",
                     status=InventoryStatus.in_stock)
    db.add(item); db.commit(); db.refresh(item)
    return item


def test_order_happy_path():
    db = _session()
    item = _seed_inventory(db, sale_price=30.0)
    order = orders.create_order(db, item.id, "KIOSK-01")
    assert order.status == OrderStatus.created
    db.refresh(item)
    assert item.status == InventoryStatus.reserved      # 下单即锁库存

    paid, pay_params = orders.pay_order(db, order.id)   # 默认 mock 支付
    assert pay_params is None                            # 同步支付无需拉起
    assert paid.status == OrderStatus.completed
    assert paid.pay_provider == "mock"
    db.refresh(item)
    assert item.status == InventoryStatus.sold          # 支付后出货已售


def test_cannot_buy_same_item_twice():
    db = _session()
    item = _seed_inventory(db)
    orders.create_order(db, item.id, "KIOSK-01")        # 第一次锁定
    try:
        orders.create_order(db, item.id, "KIOSK-01")    # 第二次应失败
        assert False, "应阻止重复下单"
    except orders.OrderError:
        pass


def test_cancel_releases_stock():
    db = _session()
    item = _seed_inventory(db)
    order = orders.create_order(db, item.id, "KIOSK-01")
    orders.cancel_order(db, order.id)
    db.refresh(item)
    assert item.status == InventoryStatus.in_stock      # 取消后库存释放


def test_recycle_payout_credits_balance():
    db = _session()
    rec = RecycleRecord(book_id=None, condition_level="good", evaluated_price=15.0)
    db.add(rec); db.commit(); db.refresh(rec)
    user = get_or_create_user(db, "openid_seller_1")
    assert float(user.balance) == 0.0
    credit_recycle_payout(db, user, 15.0, rec.id)
    db.refresh(user)
    assert float(user.balance) == 15.0                  # 回收金额到账

    entries = db.query(LedgerEntry).all()
    assert len(entries) == 1
    assert entries[0].entry_type == LedgerType.payout
    assert float(entries[0].balance_after) == 15.0


def test_balance_cannot_go_negative():
    db = _session()
    user = get_or_create_user(db, "openid_2")
    try:
        post_ledger(db, user, LedgerType.purchase, -5.0)
        assert False, "余额不足应报错"
    except Exception:
        pass


def test_seller_price_resolution():
    from app.inventory.service import resolve_payout

    # 未改价 → 用 AI 估价
    assert resolve_payout(20.0, None) == (20.0, False)
    # 改低 → 直接采用，不复核
    assert resolve_payout(20.0, 15.0) == (15.0, False)
    # 改高 → 按 AI 价到账 + 标记复核
    price, review = resolve_payout(20.0, 30.0)
    assert price == 20.0 and review is True
    # 低于下限 → 提到最低价
    assert resolve_payout(20.0, 0.0)[0] == 1.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("PASS", name)
    print("ALL TESTS PASSED")
