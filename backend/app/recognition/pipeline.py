"""识别 agent 编排：ISBN → OCR → 本地匹配 → VLM → 外部元数据。

每一步命中即返回，并带上 method 与 confidence，便于复核与调优。
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Book
from app.schemas import BookInfo, RecognizeResult
from app.vlm_client import VLMClient

from . import imaging, local_cv, matcher, metadata, vlm_recognize

logger = logging.getLogger(__name__)


def _to_info(book: Book) -> BookInfo:
    return BookInfo(
        id=book.id,
        isbn=book.isbn,
        title=book.title,
        author=book.author,
        publisher=book.publisher,
        category=book.category,
        market_price=float(book.market_price or 0),
        base_recycle_rate=float(book.base_recycle_rate or 0.35),
        source=book.source,
    )


def recognize(db: Session, image_bytes: bytes, vlm: VLMClient, review_threshold: float) -> RecognizeResult:
    frame = imaging.bytes_to_frame(image_bytes)
    texts: list[str] = []

    # 1) ISBN 条码
    isbn = local_cv.decode_isbn(frame)
    if isbn:
        book = matcher.find_book_by_isbn(db, isbn)
        if book:
            return RecognizeResult(matched=True, book=_to_info(book), method="isbn", confidence=1.0)
        # 条码读到但本地无此书 → 外部元数据
        meta = metadata.fetch_metadata(db, isbn)
        if meta:
            book = metadata.upsert_book_from_metadata(db, meta)
            return RecognizeResult(matched=True, book=_to_info(book), method="metadata_api", confidence=0.95)

    # 2) OCR → 文本模糊匹配
    ocr_text = local_cv.ocr_frame(frame)
    if ocr_text:
        texts.append(ocr_text)
        book, score = matcher.find_book_by_text(db, ocr_text)
        if book:
            return RecognizeResult(
                matched=True, book=_to_info(book), method="ocr",
                confidence=round(score, 4), recognized_text=ocr_text,
                need_review=score < review_threshold,
            )

    # 3) VLM 辅助识别 → ISBN/文本匹配 → 外部元数据
    jpeg = imaging.frame_to_jpeg(frame)
    vlm_res = vlm_recognize.recognize_with_vlm(jpeg, vlm)
    if vlm_res:
        texts.append(str(vlm_res))
        if vlm_res["isbn"]:
            book = matcher.find_book_by_isbn(db, vlm_res["isbn"])
            if not book:
                meta = metadata.fetch_metadata(db, vlm_res["isbn"])
                if meta:
                    book = metadata.upsert_book_from_metadata(db, meta)
            if book:
                conf = max(0.7, vlm_res["confidence"])
                return RecognizeResult(
                    matched=True, book=_to_info(book), method="vlm",
                    confidence=round(conf, 4), recognized_text=str(vlm_res),
                    need_review=conf < review_threshold,
                )
        combined = "\n".join([vlm_res["title"], vlm_res["author"], vlm_res["publisher"]])
        book, score = matcher.find_book_by_text(db, combined)
        if book:
            conf = round(min(score, max(0.6, vlm_res["confidence"])), 4)
            return RecognizeResult(
                matched=True, book=_to_info(book), method="vlm",
                confidence=conf, recognized_text=str(vlm_res),
                need_review=conf < review_threshold,
            )

    # 未命中
    return RecognizeResult(
        matched=False, method="none", confidence=0.0,
        recognized_text="\n".join(texts), need_review=True,
    )
