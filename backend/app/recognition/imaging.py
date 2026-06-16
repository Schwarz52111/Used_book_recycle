"""图像工具：上传字节 <-> OpenCV 帧 <-> JPEG 字节。

cv2 / numpy 采用惰性导入：只有真正用到识别时才需要安装，
这样未装 OpenCV 的环境（如尚无 wheel 的新 Python）仍能启动服务器、
使用定价/库存等接口。
"""

from __future__ import annotations


def _cv():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise RuntimeError(
            "图像识别需要 opencv-python 与 numpy，请先安装：pip install opencv-python numpy"
        ) from exc
    return cv2, np


def bytes_to_frame(data: bytes):
    """把上传的图片字节解码成 BGR 帧。"""
    cv2, np = _cv()
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("无法解码图片，请确认上传的是有效图像")
    return frame


def frame_to_jpeg(frame, max_width: int = 1200, quality: int = 88) -> bytes:
    """把帧编码成 JPEG 字节（用于发送给 VLM）。"""
    cv2, _ = _cv()
    height, width = frame.shape[:2]
    if width > max_width:
        scale = max_width / width
        frame = cv2.resize(frame, (max_width, int(height * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("图像编码失败")
    return buf.tobytes()
