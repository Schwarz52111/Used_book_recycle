import argparse
from typing import Any

import mysql.connector


BOOKS = [
    ("9787115546081", "Python编程：从入门到实践", "埃里克·马瑟斯", "人民邮电出版社", "计算机", 89.00, 45.00, 0.38),
    ("9787111213826", "算法导论", "托马斯·科尔曼", "机械工业出版社", "计算机", 128.00, 68.00, 0.35),
    ("9787508649719", "人类简史", "尤瓦尔·赫拉利", "中信出版社", "历史", 68.00, 32.00, 0.32),
    ("9787544280878", "解忧杂货店", "东野圭吾", "南海出版公司", "文学", 39.50, 18.00, 0.30),
    ("9787302423287", "数据库系统概论", "王珊、萨师煊", "高等教育出版社", "教材", 42.00, 20.00, 0.36),
    ("9787040589818", "高等数学 第八版 上册", "同济大学数学科学学院", "高等教育出版社", "教材", 49.80, 28.00, 0.36),
    ("9787040588682", "高等数学 第八版 下册", "同济大学数学科学学院", "高等教育出版社", "教材", 43.80, 24.00, 0.36),
    ("9787040604214", "高等数学习题全解指导 上册 同济·第八版", "同济大学数学科学学院", "高等教育出版社", "教材", 46.40, 26.00, 0.36),
    ("9787040604221", "高等数学习题全解指导 下册 同济·第八版", "同济大学数学科学学院", "高等教育出版社", "教材", 39.20, 22.00, 0.36),
    ("9787040599039", "毛泽东思想和中国特色社会主义理论体系概论（2023年版）", "本书编写组", "高等教育出版社", "教材", 25.00, 12.00, 0.36),
    ("9787020002207", "红楼梦", "曹雪芹、高鹗", "人民文学出版社", "文学", 59.70, 28.00, 0.30),
]


CONDITION_RULES = [
    ("like_new", "近全新，无明显折痕、污渍、缺页", 1.00),
    ("good", "轻微使用痕迹，少量折角或标注", 0.82),
    ("acceptable", "有明显磨损、标注或轻微污渍，但内容完整", 0.62),
    ("damaged", "破损、缺页、严重污渍或装订松散", 0.25),
]


SCHEMA_STATEMENTS = [
    """
    CREATE DATABASE IF NOT EXISTS used_book_recycle
      DEFAULT CHARACTER SET utf8mb4
      DEFAULT COLLATE utf8mb4_unicode_ci
    """,
    "USE used_book_recycle",
    """
    CREATE TABLE IF NOT EXISTS books (
        id INT AUTO_INCREMENT PRIMARY KEY,
        isbn VARCHAR(20) NOT NULL UNIQUE,
        title VARCHAR(255) NOT NULL,
        author VARCHAR(255) NOT NULL,
        publisher VARCHAR(255) NOT NULL,
        category VARCHAR(100) NOT NULL,
        original_price DECIMAL(10, 2) NOT NULL,
        market_price DECIMAL(10, 2) NOT NULL,
        base_recycle_rate DECIMAL(5, 2) NOT NULL DEFAULT 0.35,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS condition_rules (
        id INT AUTO_INCREMENT PRIMARY KEY,
        condition_level VARCHAR(50) NOT NULL UNIQUE,
        description VARCHAR(255) NOT NULL,
        price_factor DECIMAL(5, 2) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS recycle_records (
        id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL,
        condition_level VARCHAR(50) NOT NULL,
        damage_score DECIMAL(6, 4) NOT NULL,
        completeness_score DECIMAL(6, 4) NOT NULL,
        evaluated_price DECIMAL(10, 2) NOT NULL,
        image_path VARCHAR(255),
        recognized_text TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_recycle_records_book
            FOREIGN KEY (book_id) REFERENCES books(id)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS buyer_orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        recycle_record_id INT NOT NULL,
        buyer_name VARCHAR(100) NOT NULL,
        buyer_phone VARCHAR(50) NOT NULL,
        sale_price DECIMAL(10, 2) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        refunded_at TIMESTAMP NULL DEFAULT NULL,
        INDEX idx_buyer_orders_record_status (recycle_record_id, status),
        CONSTRAINT fk_buyer_orders_record
            FOREIGN KEY (recycle_record_id) REFERENCES recycle_records(id)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE OR REPLACE VIEW transactions AS
    SELECT
        o.id AS transaction_id,
        o.recycle_record_id,
        b.title,
        b.isbn,
        o.buyer_name,
        o.buyer_phone,
        o.sale_price,
        o.status,
        o.created_at,
        o.refunded_at
    FROM buyer_orders o
    JOIN recycle_records r ON r.id = o.recycle_record_id
    JOIN books b ON b.id = r.book_id
    """,
]


def ensure_column_exists(cursor, table_name: str, column_name: str, column_definition: str) -> None:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        (table_name, column_name),
    )
    exists = cursor.fetchone()[0] > 0
    if not exists:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def init_database(config: dict[str, Any]) -> None:
    conn = mysql.connector.connect(**config)
    try:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)

        ensure_column_exists(cursor, "recycle_records", "image_path", "VARCHAR(255)")

        cursor.executemany(
            """
            INSERT INTO books
                (isbn, title, author, publisher, category, original_price, market_price, base_recycle_rate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                author = VALUES(author),
                publisher = VALUES(publisher),
                category = VALUES(category),
                original_price = VALUES(original_price),
                market_price = VALUES(market_price),
                base_recycle_rate = VALUES(base_recycle_rate)
            """,
            BOOKS,
        )
        cursor.executemany(
            """
            INSERT INTO condition_rules
                (condition_level, description, price_factor)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                description = VALUES(description),
                price_factor = VALUES(price_factor)
            """,
            CONDITION_RULES,
        )
        conn.commit()
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="初始化二手图书回收系统 MySQL 数据库")
    parser.add_argument("--host", default="127.0.0.1", help="MySQL 地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=3306, help="MySQL 端口，默认 3306")
    parser.add_argument("--user", default="root", help="MySQL 用户名，默认 root")
    parser.add_argument("--password", default="", help="MySQL 密码")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    init_database(
        {
            "host": args.host,
            "port": args.port,
            "user": args.user,
            "password": args.password,
            "charset": "utf8mb4",
        }
    )
    print("MySQL database initialized: used_book_recycle")
