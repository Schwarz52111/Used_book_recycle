import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

import cv2
from pydantic import BaseModel, Field, ValidationError


class LocalAIBookResult(BaseModel):
    title: str = Field(default="")
    author: str = Field(default="")
    publisher: str = Field(default="")
    isbn: str = Field(default="")
    condition_level: str = Field(default="")
    damage_description: str = Field(default="")
    recycle_price_rate: float = Field(default=0.0)
    confidence: float = Field(default=0.0)

    @classmethod
    def from_payload(cls, payload: dict) -> "LocalAIBookResult":
        if hasattr(cls, "model_validate"):
            return cls.model_validate(payload)
        return cls.parse_obj(payload)

    def to_payload(self) -> dict:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()


@dataclass
class OllamaRecognizerConfig:
    host: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5vl:3b"
    enabled: bool = True
    timeout_seconds: int = 120


def encode_frame_as_base64(frame, max_width: int = 1200) -> str:
    height, width = frame.shape[:2]
    if width > max_width:
        scale = max_width / width
        frame = cv2.resize(frame, (max_width, int(height * scale)), interpolation=cv2.INTER_AREA)

    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not ok:
        raise RuntimeError("摄像头画面编码失败，无法发送给本地 AI 识别")
    return base64.b64encode(buffer).decode("utf-8")


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("本地 AI 未返回 JSON 对象")
    return json.loads(text[start : end + 1])


def recognize_book_with_ollama(frame, config: OllamaRecognizerConfig) -> Optional[LocalAIBookResult]:
    if not config.enabled:
        return None

    prompt = """
你是二手书自助回收设备的图像识别模块。请根据图片中可见的书籍封面信息识别书籍。
只根据图片可见内容回答，不确定的字段留空，不要编造。
请严格输出一个 JSON 对象，不要输出解释文字。
必须包含下面所有字段，字段名不能改，不能省略 recycle_price_rate。
JSON 字段如下：
{
  "title": "书名",
  "author": "作者、主编或编者",
  "publisher": "出版社",
  "isbn": "ISBN，若图片不可见则留空",
  "condition_level": "like_new/good/acceptable/damaged 之一，不确定留空",
  "damage_description": "封面可见破损、污渍、折角、磨损情况",
  "recycle_price_rate": 0.0,
  "confidence": 0.0到1.0之间的识别置信度
}
其中 recycle_price_rate 是基于图片品相给出的回收价系数，必须是数字。近全新0.90-1.00，良好0.75-0.90，可接受0.55-0.75，破损0.20-0.50。
如果 condition_level 是 good，recycle_price_rate 通常应在 0.75 到 0.90 之间，例如 0.85。
如果封面无明显破损、污渍或折角，condition_level 应为 good 或 like_new，recycle_price_rate 不应低于 0.80。
"""

    payload = {
        "model": config.model,
        "prompt": prompt,
        "images": [encode_frame_as_base64(frame)],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{config.host.rstrip('/')}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        print(f"本地 Ollama 请求失败：HTTP {exc.code} {detail}")
        if "not found" in detail.lower() or "model" in detail.lower():
            print(f"请确认已执行：ollama pull {config.model}")
        return None
    except urllib.error.URLError as exc:
        print(f"本地 Ollama 连接失败：{exc}")
        print("请确认 Ollama 已安装并正在运行，默认地址为 http://127.0.0.1:11434。")
        return None
    except TimeoutError:
        print("本地 Ollama 识别超时。")
        return None

    raw_text = body.get("response", "")
    try:
        parsed = extract_json_object(raw_text)
        if "recycle_price_rate" not in parsed:
            print("本地 AI 返回缺少 recycle_price_rate，已拒绝本次结果。")
            print(f"原始返回：{raw_text[:500]}")
            return None
        result = LocalAIBookResult.from_payload(parsed)
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        print(f"本地 AI 返回格式无法解析：{exc}")
        print(f"原始返回：{raw_text[:500]}")
        return None

    if not 0.2 <= result.recycle_price_rate <= 1.0:
        print(f"本地 AI 返回的 recycle_price_rate 不合理：{result.recycle_price_rate}")
        return None

    return result


def local_ai_result_to_text(result: LocalAIBookResult) -> str:
    return json.dumps(result.to_payload(), ensure_ascii=False)
