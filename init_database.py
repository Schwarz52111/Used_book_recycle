import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).with_name("used_books.db")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    publisher TEXT NOT NULL,
    category TEXT NOT NULL,
    original_price REAL NOT NULL,
    market_price REAL NOT NULL,
    base_recycle_rate REAL NOT NULL DEFAULT 0.35,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS condition_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_level TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    price_factor REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS recycle_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    condition_level TEXT NOT NULL,
    damage_score REAL NOT NULL,
    completeness_score REAL NOT NULL,
    evaluated_price REAL NOT NULL,
    recognized_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id)
);
"""


BOOKS = [
    (
        "9787115546081",
        "Python编程：从入门到实践",
        "埃里克·马瑟斯",
        "人民邮电出版社",
        "计算机",
        89.00,
        45.00,
        0.38,
    ),
    (
        "9787111213826",
        "算法导论",
        "托马斯·科尔曼",
        "机械工业出版社",
        "计算机",
        128.00,
        68.00,
        0.35,
    ),
    (
        "9787508649719",
        "人类简史",
        "尤瓦尔·赫拉利",
        "中信出版社",
        "历史",
        68.00,
        32.00,
        0.32,
    ),
    (
        "9787544280878",
        "解忧杂货店",
        "东野圭吾",
        "南海出版公司",
        "文学",
        39.50,
        18.00,
        0.30,
    ),
    (
        "9787302423287",
        "数据库系统概论",
        "王珊、萨师煊",
        "高等教育出版社",
        "教材",
        42.00,
        20.00,
        0.36,
    ),
    (
        "9787040589818",
        "高等数学 第八版 上册",
        "同济大学数学科学学院",
        "高等教育出版社",
        "教材",
        49.80,
        28.00,
        0.36,
    ),
    (
        "9787040588682",
        "高等数学 第八版 下册",
        "同济大学数学科学学院",
        "高等教育出版社",
        "教材",
        43.80,
        24.00,
        0.36,
    ),
    (
        "9787040599039",
        "毛泽东思想和中国特色社会主义理论体系概论（2023年版）",
        "本书编写组",
        "高等教育出版社",
        "教材",
        25.00,
        12.00,
        0.36,
    ),
]


CONDITION_RULES = [
    ("like_new", "近全新，无明显折痕、污渍、缺页", 1.00),
    ("good", "轻微使用痕迹，少量折角或标注", 0.82),
    ("acceptable", "有明显磨损、标注或轻微污渍，但内容完整", 0.62),
    ("damaged", "破损、缺页、严重污渍或装订松散", 0.25),
]


def init_database() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            """
            INSERT OR REPLACE INTO books
                (isbn, title, author, publisher, category, original_price, market_price, base_recycle_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            BOOKS,
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO condition_rules
                (condition_level, description, price_factor)
            VALUES (?, ?, ?)
            """,
            CONDITION_RULES,
        )
        conn.commit()


if __name__ == "__main__":
    init_database()
    print(f"Database initialized: {DB_PATH}")
