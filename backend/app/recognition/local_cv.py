"""本地识别：ISBN 条码 + OCR（复用原型思路）。"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from pyzbar.pyzbar import decode as decode_barcodes
except Exception:  # pyzbar 需要系统 zbar 库
    decode_barcodes = None

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except Exception:
    pytesseract = None
    TesseractNotFoundError = RuntimeError

_OCR_READY = False


def configure_tesseract() -> None:
    global _OCR_READY
    if pytesseract is None:
        _OCR_READY = False
        return
    cmd = get_settings().tesseract_cmd
    if cmd and Path(cmd).exists():
        pytesseract.pytesseract.tesseract_cmd = cmd
        _OCR_READY = True
        return
    current = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    _OCR_READY = shutil.which(current) is not None
    if not _OCR_READY:
        logger.info("未找到 tesseract，OCR 关闭，仅用 ISBN 条码 + VLM。")


def decode_isbn(frame) -> Optional[str]:
    if decode_barcodes is None:
        return None
    try:
        for barcode in decode_barcodes(frame):
            value = barcode.data.decode("utf-8", errors="ignore").strip()
            digits = "".join(ch for ch in value if ch.isdigit())
            if len(digits) in (10, 13):
                return digits
    except Exception as exc:
        logger.warning("条码解析异常：%s", exc)
    return None


def ocr_frame(frame) -> str:
    if pytesseract is None or not _OCR_READY:
        return ""
    import cv2

    height, width = frame.shape[:2]
    if max(height, width) < 1400:
        frame = cv2.resize(frame, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9)
    results: list[str] = []
    try:
        for image in (gray, binary, adaptive):
            for config in ("--psm 6", "--psm 11", "--psm 12"):
                value = pytesseract.image_to_string(image, lang="chi_sim+eng", config=config).strip()
                if value:
                    results.append(value)
    except TesseractNotFoundError:
        return ""
    except Exception as exc:
        logger.warning("OCR 失败已跳过：%s", exc)
        return ""
    return "\n".join(dict.fromkeys(results))
