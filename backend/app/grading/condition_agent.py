"""品相评估 agent。

用 VLM 按统一 rubric 给出各维度评分、证据、综合等级与置信度；
低置信度或严重破损时给出复核/拒收建议。这是对原型 estimate_condition()
（Canny 边缘均值 + 边框方差）的彻底替换——后者与真实书况无因果关系。
"""

from __future__ import annotations

import logging

from app.schemas import ConditionDimension, ConditionResult
from app.vlm_client import VLMClient, VLMError

logger = logging.getLogger(__name__)

# 评分维度（0=完好，1=严重）
DIMENSIONS = ["封面磨损", "书脊磨损", "污渍水渍", "划线笔记", "折角卷边", "缺页缺附件"]

_PROMPT = f"""你是二手书自助回收设备的品相评估模块。请仔细观察图片中书籍的实际状况，
按统一标准评估二手书品相。只依据图片可见内容，不要臆测。

对以下每个维度打分（0.0 表示完好无损，1.0 表示非常严重），并给出简短证据：
{", ".join(DIMENSIONS)}

然后给出：
- condition_level：在 like_new / good / acceptable / damaged 中选一个；若为盗版、严重残缺、污损无法售卖，用 reject
- completeness：完整度 0.0~1.0（1.0 表示完整无缺）
- confidence：你对本次评估的置信度 0.0~1.0
- summary：一句话总体描述

严格输出一个 JSON 对象，不要输出多余文字：
{{
  "dimensions": [{{"name": "封面磨损", "score": 0.0, "evidence": "..."}}, ...],
  "condition_level": "good",
  "completeness": 0.9,
  "confidence": 0.8,
  "summary": "..."
}}"""

_VALID_LEVELS = {"like_new", "good", "acceptable", "damaged", "reject"}


def assess_condition(
    image_jpeg: bytes,
    vlm: VLMClient,
    review_threshold: float,
) -> ConditionResult:
    try:
        data = vlm.vision_json(_PROMPT, image_jpeg)
    except (VLMError, Exception) as exc:  # noqa: BLE001 - 评估失败一律转人工复核
        logger.warning("品相评估失败，转人工复核：%s", exc)
        return ConditionResult(
            condition_level="acceptable", confidence=0.0,
            summary="自动评估失败，已转人工复核", need_review=True,
        )

    dims: list[ConditionDimension] = []
    for d in data.get("dimensions", []) or []:
        try:
            dims.append(
                ConditionDimension(
                    name=str(d.get("name", "")),
                    score=_clamp(float(d.get("score", 0.0) or 0.0)),
                    evidence=str(d.get("evidence", "")),
                )
            )
        except (TypeError, ValueError):
            continue

    overall_damage = max((dim.score for dim in dims), default=0.0)
    avg_damage = sum(dim.score for dim in dims) / len(dims) if dims else 0.0
    completeness = _clamp(float(data.get("completeness", 1.0) or 1.0))
    confidence = _clamp(float(data.get("confidence", 0.0) or 0.0))

    level = str(data.get("condition_level", "")).strip().lower()
    if level not in _VALID_LEVELS:
        level = _level_from_scores(overall_damage, avg_damage, completeness)

    rejected = level == "reject"
    need_review = confidence < review_threshold or rejected

    return ConditionResult(
        condition_level=level,
        dimensions=dims,
        overall_damage=round(overall_damage, 4),
        completeness=round(completeness, 4),
        confidence=round(confidence, 4),
        summary=str(data.get("summary", "")),
        need_review=need_review,
        rejected=rejected,
        reject_reason=str(data.get("summary", "")) if rejected else "",
    )


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _level_from_scores(overall: float, avg: float, completeness: float) -> str:
    """VLM 未给合法等级时的兜底规则。"""
    if completeness < 0.5 or overall > 0.8:
        return "damaged"
    if avg > 0.5:
        return "acceptable"
    if avg > 0.25:
        return "good"
    return "like_new"
