"""微信小程序登录：用 wx.login 拿到的 code 换取 openid。

mock 模式：直接由 code 派生一个稳定 openid，开发期无需 AppID 即可跑通登录。
wechat 模式：调用微信 jscode2session 接口，需要 WECHAT_APPID / WECHAT_SECRET。
"""

from __future__ import annotations

import hashlib
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_JSCODE2SESSION = "https://api.weixin.qq.com/sns/jscode2session"


class AuthError(RuntimeError):
    pass


def code_to_openid(code: str) -> str:
    """返回 openid。"""
    if not code:
        raise AuthError("缺少登录 code")

    settings = get_settings()
    if settings.auth_provider != "wechat":
        # 模拟：同一 code 稳定映射到同一 openid，便于本地反复登录测试
        digest = hashlib.sha1(code.encode("utf-8")).hexdigest()[:16]
        return f"mock_{digest}"

    if not settings.wechat_appid or not settings.wechat_secret:
        raise AuthError("未配置 WECHAT_APPID / WECHAT_SECRET")
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(_JSCODE2SESSION, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise AuthError(f"微信登录请求失败：{exc}") from exc

    if data.get("errcode"):
        raise AuthError(f"微信登录失败：{data.get('errcode')} {data.get('errmsg')}")
    openid = data.get("openid")
    if not openid:
        raise AuthError("微信未返回 openid")
    return openid
