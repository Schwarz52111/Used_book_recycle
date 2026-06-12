"""课程教材精准推荐测试（SQLite）。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Book, CourseTextbook, Inventory, InventoryStatus
from app.recommend.service import get_profile, set_profile, textbook_recommend


def _session():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _stock_book(db, isbn, title, cat="计算机"):
    b = Book(isbn=isbn, title=title, author="", publisher="", category=cat,
             original_price=80, market_price=40, base_recycle_rate=0.35)
    db.add(b); db.commit(); db.refresh(b)
    db.add(Inventory(book_id=b.id, condition_level="good", cost_price=12, sale_price=24,
                     machine_id="KIOSK-01", slot_code="A1", status=InventoryStatus.in_stock))
    db.commit()
    return b


def test_textbook_recommend_by_profile():
    db = _session()
    _stock_book(db, "9787111407010", "算法导论")
    _stock_book(db, "9787121401571", "线性代数")
    # 课程教材：计算机第1学期 = 算法导论
    db.add(CourseTextbook(major="计算机", semester=1, course_name="算法设计与分析", isbn="9787111407010"))
    db.commit()

    # 未设档案 → 空
    assert textbook_recommend(db, "openid_stu") == []

    set_profile(db, "openid_stu", "计算机", 1)
    assert get_profile(db, "openid_stu") == {"major": "计算机", "semester": 1}

    recs = textbook_recommend(db, "openid_stu")
    assert len(recs) == 1
    assert recs[0]["title"] == "算法导论"
    assert "算法设计与分析" in recs[0]["reason"]

    # 切到第2学期（无对应课程）→ 空
    set_profile(db, "openid_stu", "计算机", 2)
    assert textbook_recommend(db, "openid_stu") == []


if __name__ == "__main__":
    test_textbook_recommend_by_profile()
    print("ALL TESTS PASSED")
