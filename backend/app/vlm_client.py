"""统一 VLM 客户端：云 VLM（OpenAI 兼容）为主，本地 Ollama 为降级。

两个 agent（识别、品相）共用本模块，只关心"给图片+提示词，拿结构化 JSON"。
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class VLMError(RuntimeError):
    pass


def _extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出里抠出第一个 JSON 对象，容忍 ```json 包裹。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise VLMError(f"VLM 未返回 JSON 对象：{text[:200]}")
    return json.loads(text[start : end + 1])


class VLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()

    # ---- 对外：给图片+提示词，返回 JSON dict ----
    def vision_json(self, prompt: str, image_bytes: bytes, timeout: float = 60.0) -> dict[str, Any]:
        if self.s.vlm_provider == "ollama":
            raw = self._call_ollama(prompt, image_bytes, timeout)
        else:
            try:
                raw = self._call_openai_compatible(prompt, image_bytes, timeout)
            except Exception as exc:  # 云失败则尝试本地降级
                logger.warning("云 VLM 调用失败，降级到本地 Ollama：%s", exc)
                raw = self._call_ollama(prompt, image_bytes, timeout)
        return _extract_json_object(raw)

    # ---- 云：OpenAI 兼容 chat/completions ----
    def _call_openai_compatible(self, prompt: str, image_bytes: bytes, timeout: float) -> str:
        if not self.s.vlm_base_url or not self.s.vlm_api_key:
            raise VLMError("未配置云 VLM（VLM_BASE_URL / VLM_API_KEY）")
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": self.s.vlm_model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
        }
        url = self.s.vlm_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.s.vlm_api_key}"}
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ---- 本地：Ollama generate ----
    def _call_ollama(self, prompt: str, image_bytes: bytes, timeout: float) -> str:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": self.s.ollama_model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        url = self.s.ollama_host.rstrip("/") + "/api/generate"
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data.get("response", "")


def get_vlm_client() -> VLMClient:
    return VLMClient()
