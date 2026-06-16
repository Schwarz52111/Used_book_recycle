"""外部 ISBN 元数据查询 + 落库缓存。

当本地 books 表未命中时，用 ISBN 去外部接口补全书目，写入缓存并新建 Book 行，
解决"真实书几乎匹配不上"的问题。接口形态用环境变量 ISBN_METADATA_URL 配置，
约定 GET {url}?isbn=xxx 返回 JSON：title/author/publisher/category/price 等。
"""

from __future__ import annotations

import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Book, BookMetadataCache

logger = logging.getLogger(__name__)


def _cached(db: Session, isbn: str) -> dict | None:
    row = db.scalar(select(BookMetadataCache).where(BookMetadataCache.isbn == isbn))
    if row and row.payload:
        try:
            return json.loads(row.payload)
        except json.JSONDecodeError:
            return None
    return None


def fetch_metadata(db: Session, isbn: str) -> dict | None:
    """返回标准化的书目 dict，找不到返回 None。"""
    isbn = "".join(ch for ch in (isbn or "") if ch.isdigit())
    if len(isbn) not in (10, 13):
        return None

    cached = _cached(db, isbn)
    if cached is not None:
        return cached

    url = get_settings().isbn_metadata_url
    if not url:
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params={"isbn": isbn})
            resp.raise_for_status()
            raw = resp.json()
    except Exception as exc:
        logger.warning("ISBN 元数据查询失败 %s：%s", isbn, exc)
        return None

    data = _normalize(raw, isbn)
    if data:
        db.add(BookMetadataCache(isbn=isbn, payload=json.dumps(data, ensure_ascii=False)))
        db.commit()
    return data


def _normalize(raw: dict, isbn: str) -> dict | None:
    """把不同来源字段映射到统一结构。按需扩展不同 provider 的字段名。"""
    if not isinstance(raw, dict):
        return None
    body = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    title = body.get("title") or body.get("name") or ""
    if not title:
        return None
    price = body.get("price") or body.get("original_price") or 0
    try:
        price = float(str(price).replace("¥", "").replace("元", "").strip() or 0)
    except ValueError:
        price = 0.0
    return {
        "isbn": isbn,
        "title": title,
        "author": body.get("author") or body.get("authors") or "",
        "publisher": body.get("publisher") or body.get("press") or "",
        "category": body.get("category") or body.get("class") or "",
        "original_price": price,
        "market_price": round(price * 0.5, 2) if price else 0.0,  # 无市场价时按定价估
    }


def create_book_from_vlm(db: Session, data: dict) -> Book:
    """用 VLM 识别到的真实字段新建书目（库里没有对应书时），保证显示真实书名。

    无可用 ISBN 时生成占位 ISBN 以满足唯一约束；价格留空，由人工复核补全。
    """
    import uuid

    isbn = "".join(c for c in (data.get("isbn") or "") if c.isdigit())
    if len(isbn) not in (10, 13):
        isbn = "TMP" + uuid.uuid4().hex[:12]
    existing = db.scalar(select(Book).where(Book.isbn == isbn))
    if existing:
        return existing
    book = Book(
        isbn=isbn,
        title=(data.get("title") or "未知书名")[:255],
        author=data.get("author", "") or "",
        publisher=data.get("publisher", "") or "",
        category="",
        original_price=0,
        market_price=0,
        base_recycle_rate=get_settings().default_base_recycle_rate,
        source="vlm",
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def upsert_book_from_metadata(db: Session, data: dict) -> Book:
    """把元数据写入 books 表（已存在则返回现有行）。"""
    book = db.scalar(select(Book).where(Book.isbn == data["isbn"]))
    if book:
        return book
    book = Book(
        isbn=data["isbn"],
        title=data["title"],
        author=data.get("author", ""),
        publisher=data.get("publisher", ""),
        category=data.get("category", ""),
        original_price=data.get("original_price", 0) or 0,
        market_price=data.get("market_price", 0) or 0,
        base_recycle_rate=get_settings().default_base_recycle_rate,
        source="metadata_api",
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book
