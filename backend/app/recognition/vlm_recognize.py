"""VLM 辅助识别：从封面读出书名/作者/出版社/ISBN。"""

from __future__ import annotations

import logging

from app.vlm_client import VLMClient, VLMError

logger = logging.getLogger(__name__)

_PROMPT = """你是二手书自助回收设备的图像识别模块。请根据图片中可见的书籍封面信息识别书籍。
只根据图片可见内容回答，不确定的字段留空，不要编造。
严格输出一个 JSON 对象，不要输出解释文字。字段：
{
  "title": "书名",
  "author": "作者/主编/编者",
  "publisher": "出版社",
  "isbn": "ISBN，图片不可见则留空",
  "confidence": 0.0到1.0之间的识别置信度
}"""


def recognize_with_vlm(image_jpeg: bytes, vlm: VLMClient) -> dict | None:
    try:
        data = vlm.vision_json(_PROMPT, image_jpeg)
    except VLMError as exc:
        logger.warning("VLM 识别失败：%s", exc)
        return None
    except Exception as exc:
        logger.warning("VLM 识别异常：%s", exc)
        return None
    if not data.get("title") and not data.get("isbn"):
        return None
    return {
        "title": str(data.get("title", "")).strip(),
        "author": str(data.get("author", "")).strip(),
        "publisher": str(data.get("publisher", "")).strip(),
        "isbn": "".join(ch for ch in str(data.get("isbn", "")) if ch.isdigit()),
        "confidence": float(data.get("confidence", 0.0) or 0.0),
    }
