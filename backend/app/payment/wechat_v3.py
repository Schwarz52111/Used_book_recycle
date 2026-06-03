"""微信支付 v3 · JSAPI 下单 / 拉起参数签名 / 回调解密。

依赖 cryptography（仅在真实启用微信支付时需要，故采用惰性导入）。
配置见 Settings：wechat_appid / wechat_mchid / wechat_api_v3_key /
wechat_cert_serial / wechat_private_key / wechat_notify_url。

注意：本模块实现标准下单与回调解密流程；上线前还应补充对回调通知的
微信平台证书验签（TODO），并通过已备案 HTTPS 域名暴露 notify_url。
"""

from __future__ import annotations

import base64
import json
import time
import uuid

import httpx

from app.config import Settings, get_settings

API_BASE = "https://api.mch.weixin.qq.com"
JSAPI_PATH = "/v3/pay/transactions/jsapi"


class WeChatPayError(RuntimeError):
    pass


def _load_private_key(pem_or_path: str):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    data = pem_or_path or ""
    if data and not data.strip().startswith("-----BEGIN"):
        with open(data, "rb") as f:  # 当作文件路径
            raw = f.read()
    else:
        raw = data.encode("utf-8")
    return load_pem_private_key(raw, password=None)


def _sign(message: str, private_key) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    sig = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def _authorization(method: str, url_path: str, body: str, s: Settings) -> str:
    pk = _load_private_key(s.wechat_private_key)
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    message = f"{method}\n{url_path}\n{ts}\n{nonce}\n{body}\n"
    signature = _sign(message, pk)
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{s.wechat_mchid}",'
        f'nonce_str="{nonce}",signature="{signature}",timestamp="{ts}",'
        f'serial_no="{s.wechat_cert_serial}"'
    )


def jsapi_prepay(order_no: str, amount_fen: int, description: str, openid: str) -> str:
    """JSAPI 下单，返回 prepay_id。"""
    s = get_settings()
    for field in ("wechat_appid", "wechat_mchid", "wechat_api_v3_key", "wechat_cert_serial", "wechat_private_key", "wechat_notify_url"):
        if not getattr(s, field):
            raise WeChatPayError(f"微信支付未配置：{field}")

    body_dict = {
        "appid": s.wechat_appid,
        "mchid": s.wechat_mchid,
        "description": description,
        "out_trade_no": order_no,
        "notify_url": s.wechat_notify_url,
        "amount": {"total": amount_fen, "currency": "CNY"},
        "payer": {"openid": openid},
    }
    body = json.dumps(body_dict, separators=(",", ":"), ensure_ascii=False)
    headers = {
        "Authorization": _authorization("POST", JSAPI_PATH, body, s),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(API_BASE + JSAPI_PATH, content=body.encode("utf-8"), headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        raise WeChatPayError(f"微信下单失败：{exc.response.status_code} {exc.response.text}") from exc
    except Exception as exc:  # noqa: BLE001
        raise WeChatPayError(f"微信下单异常：{exc}") from exc

    prepay_id = data.get("prepay_id")
    if not prepay_id:
        raise WeChatPayError(f"微信未返回 prepay_id：{data}")
    return prepay_id


def build_pay_params(prepay_id: str) -> dict:
    """生成小程序 wx.requestPayment 所需参数（含 paySign）。"""
    s = get_settings()
    pk = _load_private_key(s.wechat_private_key)
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    package = f"prepay_id={prepay_id}"
    message = f"{s.wechat_appid}\n{ts}\n{nonce}\n{package}\n"
    pay_sign = _sign(message, pk)
    return {
        "timeStamp": ts,
        "nonceStr": nonce,
        "package": package,
        "signType": "RSA",
        "paySign": pay_sign,
    }


def decrypt_notify_resource(resource: dict) -> dict:
    """用 APIv3 密钥（AES-256-GCM）解密回调资源，返回明文 dict。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    s = get_settings()
    aesgcm = AESGCM(s.wechat_api_v3_key.encode("utf-8"))
    nonce = resource["nonce"].encode("utf-8")
    ciphertext = base64.b64decode(resource["ciphertext"])
    aad = (resource.get("associated_data") or "").encode("utf-8")
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
    return json.loads(plaintext.decode("utf-8"))
