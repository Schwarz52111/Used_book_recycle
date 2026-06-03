"""回收评估编排：识别 → 品相 → 定价 → 落库（含复核挂起）。

对应卖书主流程：用户投书拍照 → 一次调用拿到书目、品相、回收价。
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.config import get_settings
from app.grading.condition_agent import assess_condition
from app.models import Book, RecycleRecord, ReviewStatus, ReviewTask
from app.pricing.engine import evaluate_price
from app.recognition import imaging
from app.recognition.pipeline import recognize
from app.schemas import AppraiseResponse
from app.vlm_client import get_vlm_client


def appraise(db: Session, image_bytes: bytes) -> AppraiseResponse:
    settings = get_settings()
    vlm = get_vlm_client()
    threshold = settings.review_confidence_threshold

    # 1) 识别
    rec = recognize(db, image_bytes, vlm, threshold)

    # 2) 品相（无论是否匹配到书目都评估，证据可用于复核）
    jpeg = imaging.frame_to_jpeg(imaging.bytes_to_frame(image_bytes))
    cond = assess_condition(jpeg, vlm, threshold)

    # 3) 定价（需匹配到书目且未被拒收）
    price = None
    if rec.matched and rec.book and rec.book.id and not cond.rejected:
        book = db.get(Book, rec.book.id)
        if book:
            price = evaluate_price(db, book, cond.condition_level)

    # 4) 落库
    record = RecycleRecord(
        book_id=rec.book.id if (rec.book and rec.book.id) else None,
        condition_level=cond.condition_level,
        damage_score=cond.overall_damage,
        completeness_score=cond.completeness,
        evaluated_price=price.recycle_price if price else 0,
        recognized_text=rec.recognized_text[:2000],
        recognize_confidence=rec.confidence,
        condition_confidence=cond.confidence,
        pricing_reason=price.reason if price else "",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 5) 复核挂起
    review_task_id = None
    need_review = (not rec.matched) or rec.need_review or cond.need_review
    if need_review:
        reason = "reject" if cond.rejected else "low_confidence"
        task = ReviewTask(
            recycle_record_id=record.id,
            reason=reason,
            payload=json.dumps(
                {
                    "recognize": rec.model_dump(),
                    "condition": cond.model_dump(),
                    "price": price.model_dump() if price else None,
                },
                ensure_ascii=False,
            ),
            status=ReviewStatus.pending,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        review_task_id = task.id

    return AppraiseResponse(
        recognize=rec,
        condition=cond,
        price=price,
        record_id=record.id,
        review_task_id=review_task_id,
    )
