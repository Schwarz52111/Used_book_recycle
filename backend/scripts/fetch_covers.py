"""批量为书目补真实封面（写入 books.cover_url）。

按 ISBN 向 OpenLibrary 探测封面（default=false → 无封面返回 404），
仅把“确实存在”的封面地址写库；探测不到则留空，前端会回退到生成式封面。

用法（在 backend 目录，需联网）：
    python -m scripts.fetch_covers
可选：python -m scripts.fetch_covers --all   # 连已有 cover_url 的也重新探测
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

from sqlalchemy import or_, select

from app.db import get_sessionmaker
from app.models import Book

UA = {"User-Agent": "jike-xiaolv/1.0"}


def cover_for(isbn: str) -> str:
    digits = "".join(c for c in (isbn or "") if c.isdigit())
    if len(digits) not in (10, 13):
        return ""
    probe = f"https://covers.openlibrary.org/b/isbn/{digits}-L.jpg?default=false"
    try:
        req = urllib.request.Request(probe, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            if r.status == 200:
                return f"https://covers.openlibrary.org/b/isbn/{digits}-L.jpg"
    except urllib.error.HTTPError:
        return ""
    except Exception as exc:  # noqa: BLE001
        print("  网络异常：", exc)
    return ""


def main() -> None:
    refresh_all = "--all" in sys.argv
    db = get_sessionmaker()()
    try:
        stmt = select(Book)
        if not refresh_all:
            stmt = stmt.where(or_(Book.cover_url == "", Book.cover_url.is_(None)))
        books = list(db.scalars(stmt).all())
        if not books:
            print("没有需要补封面的书目。")
            return
        updated = 0
        for b in books:
            url = cover_for(b.isbn)
            if url:
                b.cover_url = url
                updated += 1
                print("✓", b.title)
            else:
                print("·", b.title, "（OpenLibrary 无封面，前端将用生成式封面）")
        db.commit()
        print(f"完成：{updated}/{len(books)} 本补到真实封面。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
