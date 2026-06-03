"""建表 + 写入品相规则与示例书目。

用法：
    python -m scripts.init_db
读取 .env 的数据库配置。仅在表不存在时建表，幂等写入种子数据。
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import Base, get_engine, get_sessionmaker
from app.models import Book, ConditionRule

CONDITION_RULES = [
    ("like_new", "近全新，无明显使用痕迹", 0.90),
    ("good", "良好，轻微使用痕迹", 0.70),
    ("acceptable", "可接受，有较明显磨损/划线", 0.50),
    ("damaged", "破损，影响阅读或品相差", 0.30),
]

SAMPLE_BOOKS = [
    # isbn, title, author, publisher, category, original, market, rate
    ("9787111213826", "深入理解计算机系统", "Randal E. Bryant", "机械工业出版社", "计算机", 139.0, 89.0, 0.35),
    ("9787115428028", "Python编程：从入门到实践", "Eric Matthes", "人民邮电出版社", "计算机", 89.0, 55.0, 0.35),
    ("9787040396638", "高等数学（上册）", "同济大学数学系", "高等教育出版社", "教材", 49.8, 28.0, 0.40),
]


def main() -> None:
    Base.metadata.create_all(get_engine())
    db = get_sessionmaker()()
    try:
        for level, desc, factor in CONDITION_RULES:
            if not db.scalar(select(ConditionRule).where(ConditionRule.condition_level == level)):
                db.add(ConditionRule(condition_level=level, description=desc, price_factor=factor))
        for isbn, title, author, pub, cat, orig, market, rate in SAMPLE_BOOKS:
            if not db.scalar(select(Book).where(Book.isbn == isbn)):
                db.add(
                    Book(
                        isbn=isbn, title=title, author=author, publisher=pub, category=cat,
                        original_price=orig, market_price=market, base_recycle_rate=rate, source="seed",
                    )
                )
        db.commit()
        print("✅ 初始化完成：表已就绪，品相规则与示例书目已写入。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
