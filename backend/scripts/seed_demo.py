"""一键演示数据：书目 / 在库 / 成交 / 回收 / 待复核，并重算热度。

用法（在 backend 目录）：
    python -m scripts.seed_demo

幂等：若 demo_user 已有成交记录则跳过，不会重复灌数。
用于演示「运营数据看板」与「个性化推荐」。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.accounts.service import credit_recycle_payout, get_or_create_user
from app.analytics.heat import recompute_heat
from app.db import Base, get_engine, get_sessionmaker
from app.models import (
    Book,
    Inventory,
    InventoryStatus,
    Order,
    OrderStatus,
    RecycleRecord,
    ReviewStatus,
    ReviewTask,
)

# isbn, title, publisher, category, original, market
BOOKS = [
    ("9787111407010", "算法导论", "机械工业出版社", "计算机", 128.0, 75.0),
    ("9787115546081", "流畅的Python", "人民邮电出版社", "计算机", 139.0, 79.0),
    ("9787544291200", "百年孤独", "南海出版公司", "文学", 55.0, 30.0),
    ("9787532776801", "了不起的盖茨比", "上海译文出版社", "文学", 39.0, 20.0),
    ("9787121401571", "线性代数", "电子工业出版社", "教材", 45.0, 22.0),
    ("9787513598200", "新概念英语2", "外语教学与研究出版社", "外语", 46.0, 24.0),
]


def main() -> None:
    Base.metadata.create_all(get_engine())
    db = get_sessionmaker()()
    try:
        buyer = get_or_create_user(db, "demo_user", "演示同学")
        if db.scalar(select(Order).where(Order.buyer_id == buyer.id)):
            print("演示数据已存在，跳过。如需重灌，请先删除 used_books.db 再 init_db。")
            return

        books = {}
        for isbn, title, pub, cat, orig, market in BOOKS:
            b = db.scalar(select(Book).where(Book.isbn == isbn))
            if not b:
                b = Book(isbn=isbn, title=title, author="", publisher=pub, category=cat,
                         original_price=orig, market_price=market, base_recycle_rate=0.35, source="demo")
                db.add(b); db.commit(); db.refresh(b)
            books[isbn] = b

        def stock(b, status=InventoryStatus.in_stock):
            it = Inventory(book_id=b.id, condition_level="good",
                           cost_price=round(float(b.market_price) * 0.3, 2),
                           sale_price=round(float(b.market_price) * 0.6, 2),
                           machine_id="KIOSK-01", slot_code="A", status=status)
            db.add(it); db.commit(); db.refresh(it)
            return it

        # 每本各上架一本在库（供浏览/推荐候选）
        for b in books.values():
            stock(b)

        # 演示滞销：两本陈旧、低热度在库，便于看板「滞销处理建议」展示
        for isbn, days in (("9787544291200", 40), ("9787532776801", 20)):
            b = books[isbn]
            db.add(
                Inventory(
                    book_id=b.id, condition_level="acceptable",
                    cost_price=round(float(b.market_price) * 0.3, 2),
                    sale_price=round(float(b.market_price) * 0.6, 2),
                    machine_id="KIOSK-01", slot_code="", status=InventoryStatus.in_stock,
                    created_at=datetime.now() - timedelta(days=days),
                )
            )
        db.commit()

        # demo_user 买过 2 本「计算机」（各单独一本，已售），驱动偏好与成交额
        for i, isbn in enumerate(("9787111407010", "9787115546081")):
            sold = stock(books[isbn], InventoryStatus.sold)
            db.add(Order(order_no=f"DEMO-{i}", inventory_id=sold.id, buyer_id=buyer.id,
                         amount=sold.sale_price, status=OrderStatus.completed,
                         pay_provider="mock", paid_at=datetime.now(), machine_id="KIOSK-01"))
        db.commit()

        # 一条回收 + 一条待复核（演示看板待复核数与复核台）
        seller = get_or_create_user(db, "demo_seller", "演示卖家")
        rec = RecycleRecord(book_id=books["9787544291200"].id, condition_level="good", evaluated_price=12.0)
        db.add(rec); db.commit(); db.refresh(rec)
        credit_recycle_payout(db, seller, 12.0, rec.id)
        db.add(ReviewTask(recycle_record_id=rec.id, reason="seller_price_higher",
                          status=ReviewStatus.pending,
                          payload='{"ai_price":12.0,"seller_price":20.0,"accepted_price":12.0}'))
        db.commit()

        recompute_heat(db)
        print("✅ 演示数据已写入：书目/在库/成交/回收/待复核，并已重算热度。")
        print("   买家 openid：demo_user（用于测试个性化推荐）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
