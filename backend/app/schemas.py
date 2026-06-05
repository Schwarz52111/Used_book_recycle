"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- 识别 ----------
class BookInfo(BaseModel):
    id: int | None = None
    isbn: str = ""
    title: str = ""
    author: str = ""
    publisher: str = ""
    category: str = ""
    market_price: float = 0.0
    base_recycle_rate: float = 0.35
    source: str = ""


class RecognizeResult(BaseModel):
    matched: bool
    book: BookInfo | None = None
    method: str = ""              # isbn | ocr | vlm | metadata_api | none
    confidence: float = 0.0
    recognized_text: str = ""
    need_review: bool = False


# ---------- 品相 ----------
class ConditionDimension(BaseModel):
    name: str                    # 维度：封面磨损/书脊/污渍/划线/折角/缺页 等
    score: float = Field(ge=0, le=1)  # 0=完好 1=严重
    evidence: str = ""


class ConditionResult(BaseModel):
    condition_level: str         # like_new | good | acceptable | damaged | reject
    dimensions: list[ConditionDimension] = []
    overall_damage: float = Field(default=0.0, ge=0, le=1)
    completeness: float = Field(default=1.0, ge=0, le=1)
    confidence: float = Field(default=0.0, ge=0, le=1)
    summary: str = ""
    need_review: bool = False
    rejected: bool = False
    reject_reason: str = ""


# ---------- 定价 ----------
class PriceResult(BaseModel):
    recycle_price: float         # 回收价（给卖家）
    sale_price: float            # 上架售价（给买家）
    currency: str = "CNY"
    reason: str = ""             # 可解释定价理由
    factors: dict[str, float] = {}


# ---------- 准入 ----------
class AdmissionInfo(BaseModel):
    accepted: bool
    throttled: bool = False
    in_stock: int = 0
    heat: float = 0.0
    reason: str = ""


# ---------- 一站式回收评估 ----------
class AppraiseResponse(BaseModel):
    recognize: RecognizeResult
    condition: ConditionResult | None = None
    price: PriceResult | None = None
    admission: AdmissionInfo | None = None
    record_id: int | None = None
    review_task_id: int | None = None


# ---------- 库存 ----------
class InventoryItem(BaseModel):
    id: int
    book_id: int
    title: str
    isbn: str
    category: str = ""
    condition_level: str
    cost_price: float = 0.0
    sale_price: float
    cover_url: str = ""
    machine_id: str
    slot_code: str
    status: str

    model_config = {"from_attributes": True}


class IntakeRequest(BaseModel):
    """确认回收入库。可带卖家 openid，用于回收到账。"""

    record_id: int
    machine_id: str
    slot_code: str = ""
    rfid_tag: str = ""
    seller_openid: str = ""   # 卖家微信 openid，填了则回收金额入其账户
    seller_phone: str = ""    # 设备端无登录时用手机号标识卖家账户
    seller_price: float | None = None  # 卖家改价；None=采用 AI 估价


class DispenseRequest(BaseModel):
    inventory_id: int
    machine_id: str


# ---------- 订单 / 账户 ----------
class OrderCreateRequest(BaseModel):
    inventory_id: int
    machine_id: str
    buyer_openid: str = ""    # 买家 openid，匿名可留空


class PayRequest(BaseModel):
    order_id: int
    provider: str | None = None   # mock | wechat，留空用默认


class OrderInfo(BaseModel):
    id: int
    order_no: str
    inventory_id: int
    amount: float
    status: str
    pay_provider: str = ""
    machine_id: str = ""

    model_config = {"from_attributes": True}


class PayResult(BaseModel):
    order: OrderInfo
    paid: bool                      # True=同步已付(mock)；False=需前端拉起支付
    pay_params: dict | None = None  # 微信小程序 wx.requestPayment 参数


class LoginRequest(BaseModel):
    code: str                 # wx.login 返回的 code
    nickname: str = ""


class UserInfo(BaseModel):
    id: int
    openid: str
    nickname: str = ""
    balance: float = 0.0
    credit_score: int = 100

    model_config = {"from_attributes": True}


class LedgerEntryInfo(BaseModel):
    id: int
    entry_type: str
    amount: float
    balance_after: float
    ref_type: str = ""
    ref_id: int | None = None
    note: str = ""

    model_config = {"from_attributes": True}
