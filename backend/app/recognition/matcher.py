"""书目匹配：ISBN 精确匹配 + 文本模糊匹配（端口自原型）。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Book

MATCH_THRESHOLD = 0.58


def normalize_text(value: str) -> str:
    return "".join(re.findall(r"[一-鿿A-Za-z0-9]+", value or "")).lower()


def partial_similarity(needle: str, haystack: str) -> float:
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0
    if haystack in needle:
        return 0.92
    if len(haystack) <= len(needle):
        return SequenceMatcher(None, needle, haystack).ratio()
    best = 0.0
    min_size = max(2, int(len(needle) * 0.7))
    max_size = min(len(haystack), int(len(needle) * 1.4) + 1)
    for size in range(min_size, max_size + 1):
        step = max(1, size // 4)
        for start in range(0, len(haystack) - size + 1, step):
            fragment = haystack[start : start + size]
            best = max(best, SequenceMatcher(None, needle, fragment).ratio())
    return best


def find_book_by_isbn(db: Session, isbn: str) -> Book | None:
    if not isbn:
        return None
    return db.scalar(select(Book).where(Book.isbn == isbn))


def find_book_by_text(db: Session, text: str) -> tuple[Book | None, float]:
    normalized = normalize_text(text)
    if not normalized:
        return None, 0.0
    best_score = 0.0
    best_book: Book | None = None
    for book in db.scalars(select(Book)).all():
        candidates = [
            book.title,
            book.author,
            book.publisher,
            f"{book.title}{book.author}",
            f"{book.title}{book.publisher}",
        ]
        for cand in candidates:
            score = partial_similarity(normalize_text(cand), normalized)
            if score > best_score:
                best_score, best_book = score, book
    if best_book and best_score >= MATCH_THRESHOLD:
        return best_book, best_score
    return None, best_score
