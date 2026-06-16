"""支付提供方抽象。

和出货接口同思路：用抽象接口隔离"真实微信支付"和"开发期模拟支付"。
拿到商户号/API密钥/证书后，把 WeChatPayProvider 的 TODO 补全即可，业务层不动。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PaymentIntent:
    """发起支付的返回：给前端用于拉起支付。"""

    ok: bool
    provider: str
    txn_id: str = ""                  # 第三方流水号 / prepay_id
    status: str = "pending"           # pending | paid | failed
    pay_params: dict = field(default_factory=dict)  # 小程序/JSAPI 拉起参数 或 二维码串
    message: str = ""


class PaymentProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def create_payment(self, order_no: str, amount: float, description: str, openid: str = "") -> PaymentIntent:
        """发起支付。返回拉起支付所需信息。"""

    @abstractmethod
    def query_payment(self, order_no: str) -> str:
        """查询支付状态：pending | paid | failed。"""


class MockPaymentProvider(PaymentProvider):
    """开发/演示用：发起即视为支付成功。"""

    name = "mock"

    def create_payment(self, order_no: str, amount: float, description: str, openid: str = "") -> PaymentIntent:
        logger.info("[mock-pay] 订单 %s 金额 %.2f 模拟支付成功", order_no, amount)
        return PaymentIntent(ok=True, provider=self.name, txn_id="MOCK-" + order_no, status="paid",
                             message="模拟支付成功")

    def query_payment(self, order_no: str) -> str:
        return "paid"


class WeChatPayProvider(PaymentProvider):
    """微信支付（JSAPI/小程序下单）。待填商户凭证后启用。

    需要的配置（建议放 .env）：
      WECHAT_APPID        小程序 AppID
      WECHAT_MCHID        商户号
      WECHAT_API_V3_KEY   APIv3 密钥
      WECHAT_CERT_SERIAL  商户证书序列号
      WECHAT_PRIVATE_KEY  商户私钥（路径或内容）
      WECHAT_NOTIFY_URL   支付结果回调（需已备案的 HTTPS 域名）
    """

    name = "wechat"

    def create_payment(self, order_no: str, amount: float, description: str, openid: str = "") -> PaymentIntent:
        from app.payment.wechat_v3 import build_pay_params, jsapi_prepay

        if not openid:
            return PaymentIntent(ok=False, provider=self.name, status="failed", message="缺少买家 openid")
        amount_fen = int(round(float(amount) * 100))
        prepay_id = jsapi_prepay(order_no, amount_fen, description or "二手书购买", openid)
        params = build_pay_params(prepay_id)
        # 异步支付：返回拉起参数，真正"已支付"由回调通知确认
        return PaymentIntent(ok=True, provider=self.name, txn_id=prepay_id, status="pending", pay_params=params)

    def query_payment(self, order_no: str) -> str:
        # TODO: 调用微信支付「查询订单」接口确认状态（可用于对账兜底）
        return "pending"


_REGISTRY: dict[str, type[PaymentProvider]] = {
    MockPaymentProvider.name: MockPaymentProvider,
    WeChatPayProvider.name: WeChatPayProvider,
}


def get_payment_provider(name: str = "mock") -> PaymentProvider:
    cls = _REGISTRY.get(name, MockPaymentProvider)
    return cls()
