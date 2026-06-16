"""微信支付回调。

微信支付成功后会异步 POST 通知到此端点（notify_url）。我们用 APIv3 密钥解密资源，
确认 out_trade_no 与 trade_state，再把订单置为已付并出货。需返回 {"code":"SUCCESS"}。

注意：生产环境还应校验通知的微信平台证书签名（Wechatpay-Signature 等头），此处为 TODO。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.orders import service as orders

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payment"])


@router.post("/pay/wechat/notify")
async def wechat_notify(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        resource = body.get("resource") or {}
        # TODO: 先用微信平台证书验签 request 头，再解密
        from app.payment.wechat_v3 import decrypt_notify_resource

        data = decrypt_notify_resource(resource)
        out_trade_no = data.get("out_trade_no")
        trade_state = data.get("trade_state")
        txn_id = data.get("transaction_id")

        if trade_state == "SUCCESS" and out_trade_no:
            orders.settle_by_order_no(db, out_trade_no, txn_id)
        return JSONResponse({"code": "SUCCESS", "message": "成功"})
    except Exception as exc:  # noqa: BLE001 - 通知失败需让微信重试
        logger.exception("微信支付回调处理失败：%s", exc)
        return JSONResponse(status_code=500, content={"code": "FAIL", "message": "处理失败"})
